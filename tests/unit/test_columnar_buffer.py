from marsdisk.runtime.history import ColumnarBuffer


def test_columnar_buffer_basic():
    buf = ColumnarBuffer()
    buf.append_row({"a": 1})
    buf.append_row({"b": 2})
    assert buf.row_count == 2
    table = buf.to_table(ensure_columns=["a", "b", "c"])
    assert table.column_names[:3] == ["a", "b", "c"]
    assert table.num_rows == 2
    assert table.column("c").to_pylist() == [None, None]
    buf.set_column_constant("d", 3)
    assert buf.to_table().column("d").to_pylist() == [3, 3]
    buf.clear()
    assert len(buf) == 0


def test_columnar_buffer_extend():
    buf_left = ColumnarBuffer()
    buf_left.append_row({"a": 1})
    buf_right = ColumnarBuffer()
    buf_right.append_row({"a": 2, "b": 3})
    buf_left.extend_buffer(buf_right)
    table = buf_left.to_table(ensure_columns=["a", "b"])
    assert table.column("a").to_pylist() == [1, 2]
    assert table.column("b").to_pylist() == [None, 3]
