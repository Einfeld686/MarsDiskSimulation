#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import ArrayObject, FloatObject, NameObject, NullObject


def _as_float_or_null(value):
    if value is None or isinstance(value, NullObject):
        return NullObject()
    return FloatObject(value)


def _dest_to_array(dest) -> ArrayObject:
    typ = dest.typ if dest.typ else "/XYZ"
    left = _as_float_or_null(dest.left)
    top = _as_float_or_null(dest.top)
    zoom = _as_float_or_null(dest.zoom)
    arr = ArrayObject([dest.page, NameObject(typ), left, top, zoom])
    return arr


def _rebuild_outlines(reader: PdfReader, writer: PdfWriter) -> int:
    try:
        outlines = reader.outline
    except Exception:
        return 0

    def walk(items, parent=None):
        count = 0
        last = None
        for item in items:
            if isinstance(item, list):
                if last is not None:
                    count += walk(item, parent=last)
                continue
            title = getattr(item, "title", None)
            if title is None:
                title = str(item)
            try:
                page_index = reader.get_destination_page_number(item)
            except Exception:
                last = None
                continue
            last = writer.add_outline_item(title, page_index, parent=parent)
            count += 1
        return count

    return walk(outlines)


def resolve_links(input_path: Path, output_path: Path) -> int:
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    root = writer._root_object
    reader_root = reader.trailer["/Root"]

    if "/PageMode" in reader_root:
        root[NameObject("/PageMode")] = reader_root["/PageMode"]
    if "/PageLabels" in reader_root:
        root[NameObject("/PageLabels")] = reader_root["/PageLabels"].clone(writer)

    root[NameObject("/OpenAction")] = ArrayObject(
        [writer.pages[0].indirect_reference, NameObject("/Fit")]
    )

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    dest_map = {}
    for name, dest in reader.named_destinations.items():
        try:
            page_index = reader.get_destination_page_number(dest)
        except Exception:
            continue
        dest_map[name] = (page_index, dest.typ, dest.left, dest.top, dest.zoom)

    updated = 0
    for page in writer.pages:
        if "/Annots" not in page:
            continue
        for annot_ref in page["/Annots"]:
            annot = annot_ref.get_object()
            if annot.get("/Subtype") != "/Link":
                continue
            action = annot.get("/A")
            if action:
                dest_name = action.get("/D")
                if isinstance(dest_name, str) and dest_name in dest_map:
                    page_index, typ, left, top, zoom = dest_map[dest_name]
                    target_page = writer.pages[page_index]
                    typ = typ if typ else "/XYZ"
                    dest_array = ArrayObject(
                        [
                            target_page.indirect_reference,
                            NameObject(typ),
                            _as_float_or_null(left),
                            _as_float_or_null(top),
                            _as_float_or_null(zoom),
                        ]
                    )
                    action[NameObject("/D")] = dest_array
                    updated += 1
            else:
                dest_name = annot.get("/Dest")
                if isinstance(dest_name, str) and dest_name in dest_map:
                    page_index, typ, left, top, zoom = dest_map[dest_name]
                    target_page = writer.pages[page_index]
                    typ = typ if typ else "/XYZ"
                    dest_array = ArrayObject(
                        [
                            target_page.indirect_reference,
                            NameObject(typ),
                            _as_float_or_null(left),
                            _as_float_or_null(top),
                            _as_float_or_null(zoom),
                        ]
                    )
                    annot[NameObject("/Dest")] = dest_array
                    updated += 1

    outline_total = _rebuild_outlines(reader, writer)
    if outline_total == 0:
        print("resolve_links: warning: no outlines rebuilt")

    tmp_path = output_path
    if input_path.resolve() == output_path.resolve():
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    with tmp_path.open("wb") as f:
        writer.write(f)

    if tmp_path != output_path:
        tmp_path.replace(output_path)

    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve named destinations into explicit arrays in link annotations."
    )
    parser.add_argument("--in", dest="input_path", required=True, help="Input PDF")
    parser.add_argument("--out", dest="output_path", required=True, help="Output PDF")
    args = parser.parse_args()

    updated = resolve_links(Path(args.input_path), Path(args.output_path))
    print(f"updated_link_annots={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
