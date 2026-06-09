use pyo3::{create_exception, exceptions::PyException};

create_exception!(_core, TakumiError, PyException);
create_exception!(_core, HtmlParseError, TakumiError);
create_exception!(_core, NodeValidationError, TakumiError);
create_exception!(_core, NodeDecodeError, TakumiError);
create_exception!(_core, StyleSheetError, TakumiError);
create_exception!(_core, RenderError, TakumiError);
create_exception!(_core, UnsupportedFormatError, TakumiError);
