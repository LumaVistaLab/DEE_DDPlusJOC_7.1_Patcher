from __future__ import annotations

import argparse
import bisect
import json
import re
import struct
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from common import load_config, repo_path, sha256_file, timestamp_id, utc_now, write_json

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
except ImportError as exc:  # pragma: no cover - exercised by CLI environment
    raise SystemExit(
        "reverse-analysis dependencies are missing; run "
        "automation\\.venv\\Scripts\\python -m pip install -r automation\\requirements.txt"
    ) from exc


ASCII_RE = re.compile(rb"[\x20-\x7e]{5,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){5,}")


def section_name(section: Any) -> str:
    return section.Name.rstrip(b"\0").decode("ascii", errors="replace")


def extract_strings(pe: Any, data: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for encoding, pattern in (("ascii", ASCII_RE), ("utf-16le", UTF16_RE)):
        for match in pattern.finditer(data):
            raw = match.group(0)
            text = raw.decode(encoding, errors="replace")
            offset = match.start()
            try:
                rva = pe.get_rva_from_offset(offset)
            except Exception:
                continue
            records.append({
                "encoding": encoding,
                "text": text,
                "file_offset": offset,
                "rva": rva,
                "va": pe.OPTIONAL_HEADER.ImageBase + rva,
                "byte_length": len(raw),
            })
    return records


def runtime_functions(pe: Any, data: bytes) -> list[dict[str, int]]:
    functions: list[dict[str, int]] = []
    pdata = next((section for section in pe.sections if section_name(section) == ".pdata"), None)
    if pdata is None:
        return functions
    start = pdata.PointerToRawData
    end = min(len(data), start + pdata.SizeOfRawData)
    for offset in range(start, end - 11, 12):
        begin, finish, unwind = struct.unpack_from("<III", data, offset)
        if not begin and not finish and not unwind:
            continue
        if begin >= finish or finish > pe.OPTIONAL_HEADER.SizeOfImage:
            continue
        functions.append({"begin_rva": begin, "end_rva": finish, "unwind_rva": unwind})
    functions.sort(key=lambda item: item["begin_rva"])
    return functions


class FunctionIndex:
    def __init__(self, functions: list[dict[str, int]], image_base: int) -> None:
        self.functions = functions
        self.image_base = image_base
        self.starts = [item["begin_rva"] for item in functions]

    def containing_rva(self, rva: int) -> int | None:
        index = bisect.bisect_right(self.starts, rva) - 1
        if index < 0:
            return None
        function = self.functions[index]
        if function["begin_rva"] <= rva < function["end_rva"]:
            return function["begin_rva"]
        return None

    def containing_va(self, va: int) -> int | None:
        rva = va - self.image_base
        begin = self.containing_rva(rva)
        return self.image_base + begin if begin is not None else None

    def record_for_va(self, va: int) -> dict[str, int] | None:
        rva = va - self.image_base
        begin = self.containing_rva(rva)
        if begin is None:
            return None
        index = bisect.bisect_left(self.starts, begin)
        return self.functions[index]


def executable_sections(pe: Any) -> Iterable[Any]:
    image_scn_mem_execute = 0x20000000
    for section in pe.sections:
        if section.Characteristics & image_scn_mem_execute:
            yield section


def pointer_aliases(pe: Any, data: bytes, records: list[dict[str, Any]]) -> dict[int, list[int]]:
    aliases: dict[int, list[int]] = defaultdict(list)
    for record in records:
        needle = struct.pack("<Q", record["va"])
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            try:
                alias_rva = pe.get_rva_from_offset(offset)
            except Exception:
                start = offset + 1
                continue
            aliases[pe.OPTIONAL_HEADER.ImageBase + alias_rva].append(record["va"])
            start = offset + 1
    return dict(aliases)


def instruction_target(insn: Any) -> int | None:
    if not insn.operands:
        return None
    operand = insn.operands[0]
    if operand.type == X86_OP_IMM:
        return int(operand.imm)
    return None


def collect_xrefs_and_calls(
    pe: Any,
    data: bytes,
    functions: FunctionIndex,
    interesting_vas: set[int],
) -> tuple[list[dict[str, Any]], set[tuple[int, int]], list[dict[str, int]]]:
    disassembler = Cs(CS_ARCH_X86, CS_MODE_64)
    disassembler.detail = True
    # PE executable sections contain alignment bytes and occasional embedded
    # data. Without skipdata Capstone stops at the first undecodable byte and
    # silently misses most later xrefs.
    disassembler.skipdata = True
    xrefs: list[dict[str, Any]] = []
    calls: set[tuple[int, int]] = set()
    call_sites: list[dict[str, int]] = []

    for section in executable_sections(pe):
        code = section.get_data()
        start_va = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
        for insn in disassembler.disasm(code, start_va):
            if insn.id == 0:
                continue
            source_function = functions.containing_va(insn.address)
            if insn.mnemonic == "call":
                target = instruction_target(insn)
                if target is not None and source_function is not None:
                    destination_function = functions.containing_va(target)
                    if destination_function is not None:
                        calls.add((source_function, destination_function))
                        call_sites.append({
                            "instruction_va": insn.address,
                            "source_function_va": source_function,
                            "target_function_va": destination_function,
                        })
            targets: set[int] = set()
            for operand in insn.operands:
                if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                    targets.add(insn.address + insn.size + operand.mem.disp)
                elif operand.type == X86_OP_IMM:
                    targets.add(int(operand.imm))
            for target in targets & interesting_vas:
                xrefs.append({
                    "instruction_va": insn.address,
                    "instruction_rva": insn.address - pe.OPTIONAL_HEADER.ImageBase,
                    "function_va": source_function,
                    "target_va": target,
                    "mnemonic": insn.mnemonic,
                    "op_str": insn.op_str,
                    "bytes": insn.bytes.hex(" "),
                })
    return xrefs, calls, call_sites


def find_channel_mode_mappers(
    pe: Any,
    data: bytes,
    functions: list[dict[str, int]],
    call_sites: list[dict[str, int]],
) -> list[dict[str, Any]]:
    """Find the exact three-state mapper observed for JOC channel mode.

    The mapper accepts external values 0x0C/0x0E/0x10 and stores internal
    enum values 0/1/2 at object offset +8. Requiring all six byte patterns in
    one x64 runtime function keeps this detector narrow and reproducible.
    """

    required = (
        bytes.fromhex("48 83 FA 0C"),
        bytes.fromhex("48 83 FA 0E"),
        bytes.fromhex("48 83 FA 10"),
        bytes.fromhex("C7 41 08 00 00 00 00"),
        bytes.fromhex("C7 41 08 01 00 00 00"),
        bytes.fromhex("C7 41 08 02 00 00 00"),
    )
    image_base = pe.OPTIONAL_HEADER.ImageBase
    results: list[dict[str, Any]] = []
    for function in functions:
        length = function["end_rva"] - function["begin_rva"]
        if length <= 0 or length > 0x1000:
            continue
        try:
            offset = pe.get_offset_from_rva(function["begin_rva"])
        except Exception:
            continue
        body = data[offset : offset + length]
        if not all(pattern in body for pattern in required):
            continue
        function_va = image_base + function["begin_rva"]
        callers = [site for site in call_sites if site["target_function_va"] == function_va]
        results.append({
            "function_va": function_va,
            "function_rva": function["begin_rva"],
            "function_file_offset": offset,
            "external_to_internal_values": {"0x0C": 0, "0x0E": 1, "0x10": 2},
            "callers": callers,
            "semantic_status": (
                "strong structural candidate for 5.X/7.X/5.X+2; exact semantic order "
                "must be confirmed dynamically"
            ),
        })
    return results


def expand_relevant_functions(seeds: set[int], calls: set[tuple[int, int]], depth: int = 2) -> set[int]:
    outgoing: dict[int, set[int]] = defaultdict(set)
    incoming: dict[int, set[int]] = defaultdict(set)
    for source, target in calls:
        outgoing[source].add(target)
        incoming[target].add(source)
    result = set(seeds)
    queue = deque((seed, 0) for seed in seeds)
    while queue:
        function, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for neighbor in outgoing[function] | incoming[function]:
            if neighbor not in result:
                result.add(neighbor)
                queue.append((neighbor, current_depth + 1))
    return result


def disassemble_function(pe: Any, data: bytes, record: dict[str, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    begin_rva = record["begin_rva"]
    end_rva = record["end_rva"]
    try:
        offset = pe.get_offset_from_rva(begin_rva)
    except Exception:
        return [], []
    code = data[offset : offset + (end_rva - begin_rva)]
    disassembler = Cs(CS_ARCH_X86, CS_MODE_64)
    disassembler.detail = True
    image_base = pe.OPTIONAL_HEADER.ImageBase
    instructions: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for insn in disassembler.disasm(code, image_base + begin_rva):
        item = {
            "va": insn.address,
            "rva": insn.address - image_base,
            "bytes": insn.bytes.hex(" "),
            "mnemonic": insn.mnemonic,
            "op_str": insn.op_str,
        }
        instructions.append(item)
        immediates = [int(operand.imm) for operand in insn.operands if operand.type == X86_OP_IMM]
        has_memory = any(operand.type == X86_OP_MEM for operand in insn.operands)
        small = [value for value in immediates if -1 <= value <= 64]
        if small and (has_memory or insn.mnemonic in {"cmp", "test", "and", "or", "xor"}):
            candidates.append({**item, "small_immediates": small})
    return instructions, candidates


def diff_ranges(original: bytes, candidate: bytes) -> list[dict[str, Any]]:
    if len(original) != len(candidate):
        return [{"kind": "size_change", "original_size": len(original), "candidate_size": len(candidate)}]
    ranges: list[dict[str, Any]] = []
    start: int | None = None
    for index, (left, right) in enumerate(zip(original, candidate)):
        if left != right and start is None:
            start = index
        elif left == right and start is not None:
            ranges.append({
                "file_offset": start,
                "length": index - start,
                "original": original[start:index].hex(" "),
                "candidate": candidate[start:index].hex(" "),
            })
            start = None
    if start is not None:
        ranges.append({
            "file_offset": start,
            "length": len(original) - start,
            "original": original[start:].hex(" "),
            "candidate": candidate[start:].hex(" "),
        })
    return ranges


def markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Automated DD+ JOC downstream reverse-analysis report",
        "",
        f"Generated: {analysis['generated_at']}",
        "",
        "Scope: flat 7.1 coded/downmix layout only. Dolby Surround EX flag patching is excluded.",
        "",
        "## Binary",
        "",
        f"- SHA-256: `{analysis['binary']['sha256']}`",
        f"- Image base: `0x{analysis['binary']['image_base']:X}`",
        f"- Runtime functions: {analysis['summary']['runtime_functions']}",
        f"- Direct call edges: {analysis['summary']['direct_call_edges']}",
        f"- Target string records: {analysis['summary']['target_string_records']}",
        f"- Target xrefs: {analysis['summary']['target_xrefs']}",
        f"- Relevant functions: {analysis['summary']['relevant_functions']}",
        "",
        "## Target xrefs",
        "",
        "| Target text | String VA | Xref VA | Function VA | Instruction |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for item in analysis["target_xrefs"]:
        function = "" if item["function_va"] is None else f"0x{item['function_va']:X}"
        lines.append(
            f"| {item['target_text'].replace('|', '/')} | 0x{item['string_va']:X} | "
            f"0x{item['instruction_va']:X} | {function} | `{item['mnemonic']} {item['op_str']}` |"
        )
    if not analysis["target_xrefs"]:
        lines.append("| _No direct or pointer-table xrefs found_ | | | | |")

    lines.extend(["", "## Relevant functions", ""])
    for item in analysis["relevant_functions"]:
        lines.append(
            f"- `0x{item['va']:X}` / RVA `0x{item['rva']:X}` — "
            f"{item['instruction_count']} instructions, {item['candidate_site_count']} small-immediate sites, "
            f"listing `{item['listing']}`"
        )
    lines.extend(["", "## Automatically detected three-state channel-mode mappers", ""])
    for mapper in analysis["channel_mode_mappers"]:
        lines.append(
            f"- Mapper `0x{mapper['function_va']:X}`: `0x0C -> 0`, `0x0E -> 1`, "
            f"`0x10 -> 2`; {len(mapper['callers'])} direct caller site(s)."
        )
        for caller in mapper["callers"]:
            lines.append(
                f"  - caller `0x{caller['source_function_va']:X}` at instruction "
                f"`0x{caller['instruction_va']:X}`"
            )
    if not analysis["channel_mode_mappers"]:
        lines.append("- No exact mapper signature found.")
    lines.extend([
        "",
        "## Interpretation boundary",
        "",
        "Small immediate values are only triage candidates. A value is not treated as the final 5.X/7.X/5.X+2 selector until all writers, readers, validation paths, channel-map construction, and controlled bitstream behavior agree.",
        "",
    ])
    return "\n".join(lines)


def analyze(config_path: Path | None, output_root: Path | None, call_depth: int = 1) -> Path:
    config = load_config(config_path)
    source = repo_path(config["paths"]["original_dll"], must_exist=True)
    data = source.read_bytes()
    source_hash = sha256_file(source)
    if source_hash != config["expected_original_sha256"]:
        raise RuntimeError(f"unsupported original DLL: {source_hash}")

    pe = pefile.PE(data=data, fast_load=False)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    strings = extract_strings(pe, data)
    targets = config["reverse_targets"]
    matched: list[dict[str, Any]] = []
    for record in strings:
        matching_targets = [target for target in targets if target.casefold() in record["text"].casefold()]
        if matching_targets:
            matched.append({**record, "matching_targets": matching_targets})

    aliases = pointer_aliases(pe, data, matched)
    interesting_vas = {item["va"] for item in matched} | set(aliases)
    functions_list = runtime_functions(pe, data)
    functions = FunctionIndex(functions_list, image_base)
    xrefs, calls, call_sites = collect_xrefs_and_calls(pe, data, functions, interesting_vas)
    channel_mode_mappers = find_channel_mode_mappers(pe, data, functions_list, call_sites)

    strings_by_va = {item["va"]: item for item in matched}
    resolved_xrefs: list[dict[str, Any]] = []
    for xref in xrefs:
        target_vas = aliases.get(xref["target_va"], [xref["target_va"]])
        for target_va in target_vas:
            string = strings_by_va.get(target_va)
            if string is None:
                continue
            resolved_xrefs.append({
                **xref,
                "string_va": target_va,
                "string_rva": target_va - image_base,
                "target_text": string["text"],
                "matching_targets": string["matching_targets"],
                "via_pointer_table": xref["target_va"] != target_va,
            })

    seed_functions = {item["function_va"] for item in resolved_xrefs if item["function_va"] is not None}
    for mapper in channel_mode_mappers:
        seed_functions.add(mapper["function_va"])
        seed_functions.update(site["source_function_va"] for site in mapper["callers"])
    relevant = expand_relevant_functions(seed_functions, calls, depth=call_depth)
    run_id = f"{timestamp_id()}_{source_hash[:12]}"
    destination = output_root.resolve() if output_root else repo_path(config["paths"]["evidence_dir"]) / "reverse" / run_id
    destination.mkdir(parents=True, exist_ok=False)
    listing_dir = destination / "functions"
    listing_dir.mkdir()

    function_reports: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    for function_va in sorted(relevant):
        record = functions.record_for_va(function_va)
        if record is None:
            continue
        instructions, candidates = disassemble_function(pe, data, record)
        listing_name = f"sub_{function_va:016X}.asm"
        listing_path = listing_dir / listing_name
        listing_path.write_text(
            "\n".join(
                f"{item['va']:016X}  {item['bytes']:<32} {item['mnemonic']:<9} {item['op_str']}"
                for item in instructions
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        for candidate in candidates:
            all_candidates.append({"function_va": function_va, **candidate})
        function_reports.append({
            "va": function_va,
            "rva": function_va - image_base,
            "end_va": image_base + record["end_rva"],
            "instruction_count": len(instructions),
            "candidate_site_count": len(candidates),
            "listing": f"functions/{listing_name}",
        })

    variants: list[dict[str, Any]] = []
    for case in config["cases"]:
        path = repo_path(case["candidate_dll"], must_exist=True)
        candidate_data = path.read_bytes()
        ranges = diff_ranges(data, candidate_data)
        for item in ranges:
            if "file_offset" in item:
                try:
                    item["rva"] = pe.get_rva_from_offset(item["file_offset"])
                    item["va"] = image_base + item["rva"]
                except Exception:
                    pass
        variants.append({
            "id": case["id"],
            "path": str(path),
            "sha256": sha256_file(path),
            "diff_ranges": ranges,
        })

    sections = [{
        "name": section_name(section),
        "rva": section.VirtualAddress,
        "virtual_size": section.Misc_VirtualSize,
        "file_offset": section.PointerToRawData,
        "raw_size": section.SizeOfRawData,
        "characteristics": section.Characteristics,
    } for section in pe.sections]
    analysis = {
        "generated_at": utc_now(),
        "scope": config["scope"],
        "binary": {
            "path": str(source),
            "size": len(data),
            "sha256": source_hash,
            "image_base": image_base,
            "entry_point_rva": pe.OPTIONAL_HEADER.AddressOfEntryPoint,
            "sections": sections,
        },
        "summary": {
            "all_strings": len(strings),
            "target_string_records": len(matched),
            "pointer_aliases": len(aliases),
            "runtime_functions": len(functions_list),
            "direct_call_edges": len(calls),
            "target_xrefs": len(resolved_xrefs),
            "seed_functions": len(seed_functions),
            "relevant_functions": len(function_reports),
            "small_immediate_candidates": len(all_candidates),
            "channel_mode_mappers": len(channel_mode_mappers),
        },
        "target_strings": matched,
        "pointer_aliases": [{"alias_va": key, "string_vas": value} for key, value in sorted(aliases.items())],
        "target_xrefs": sorted(resolved_xrefs, key=lambda item: (item["target_text"], item["instruction_va"])),
        "relevant_functions": function_reports,
        "small_immediate_candidates": all_candidates,
        "channel_mode_mappers": channel_mode_mappers,
        "relevant_call_edges": [
            {"source_va": source_va, "target_va": target_va}
            for source_va, target_va in sorted(calls)
            if source_va in relevant or target_va in relevant
        ],
        "known_patch_sites": config["known_patch_sites"],
        "variant_diffs": variants,
    }
    write_json(destination / "analysis.json", analysis)
    (destination / "report.md").write_text(markdown_report(analysis), encoding="utf-8", newline="\n")
    print(json.dumps(analysis["summary"], indent=2))
    print(f"evidence: {destination}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated downstream JOC/OAMD static triage")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--call-depth", type=int, default=1, choices=(0, 1, 2))
    args = parser.parse_args()
    analyze(args.config, args.output, call_depth=args.call_depth)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"reverse-analysis error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
