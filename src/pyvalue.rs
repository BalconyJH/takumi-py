//! A narrow Python value tree that implements Serde without reviving Python integers.
//!
//! Takumi owns the schema. This adapter only exposes the JSON-like Python shapes its
//! deserializers understand, preserving mapping order and converting buffers directly
//! to owned bytes.

use std::{collections::HashSet, fmt, mem};

use pyo3::{
  Bound, PyAny, PyResult,
  exceptions::PyValueError,
  prelude::*,
  types::{
    PyBool, PyByteArray, PyByteArrayMethods, PyBytes, PyDict, PyFloat, PyInt, PyList, PyMemoryView,
    PyString, PyTuple,
  },
};
use serde::de::{
  self, DeserializeOwned, Deserializer, EnumAccess, MapAccess, SeqAccess, VariantAccess, Visitor,
  value::Error,
};

/// Decode `value` through this adapter, then hand the owned value to `T`'s Serde schema.
pub(crate) fn from_pyobject<T: DeserializeOwned + Send + 'static>(
  value: &Bound<'_, PyAny>,
  max_depth: usize,
) -> PyResult<T> {
  let py = value.py();
  let Snapshot {
    value,
    deepest: depth,
    nested_css,
  } = Value::from_pyobject(value, max_depth)?;
  py.detach(move || {
    crate::stack::run(depth >= CONTROLLED_STACK_DEPTH || nested_css, move || {
      deserialize_value(value)
    })
    .and_then(|result| result)
  })
  .map_err(PyValueError::new_err)
}

/// The schema decoder is recursive even though snapshot construction is not.
const CONTROLLED_STACK_DEPTH: usize = crate::stack::DEEP_NODE_DEPTH * 2;

#[derive(Debug)]
enum Value {
  Null,
  Bool(bool),
  I64(i64),
  U64(u64),
  F64(f64),
  String(String),
  Bytes(Vec<u8>),
  Seq(SequenceValues),
  Map(MappingEntries),
}

#[derive(Debug)]
struct SequenceValues(Vec<Value>);

#[derive(Debug)]
struct MappingEntries(Vec<(Value, Value)>);

struct Snapshot {
  value: Value,
  deepest: usize,
  nested_css: bool,
}

enum Task<'py> {
  Visit {
    value: Bound<'py, PyAny>,
    depth: usize,
  },
  FinishSequence {
    identity: usize,
    item_count: usize,
  },
  FinishMapping {
    identity: usize,
    entry_count: usize,
  },
}

impl Value {
  fn from_pyobject(value: &Bound<'_, PyAny>, max_depth: usize) -> PyResult<Snapshot> {
    let mut tasks = vec![Task::Visit {
      value: value.clone(),
      depth: 0,
    }];
    let mut active = HashSet::new();
    let mut values = Vec::new();
    let mut deepest = 0;
    let mut nested_css = false;

    while let Some(task) = tasks.pop() {
      match task {
        Task::Visit { value, depth } => {
          deepest = deepest.max(depth);

          if let Ok(dict) = value.cast::<PyDict>() {
            let entries = dict.iter().collect::<Vec<_>>();
            let identity = Self::enter_container(&value, depth, max_depth, &mut active)?;
            tasks.push(Task::FinishMapping {
              identity,
              entry_count: entries.len(),
            });
            for (key, item) in entries.into_iter().rev() {
              tasks.push(Task::Visit {
                value: item,
                depth: depth + 1,
              });
              tasks.push(Task::Visit {
                value: key,
                depth: depth + 1,
              });
            }
            continue;
          }

          if let Ok(list) = value.cast::<PyList>() {
            Self::start_sequence(
              &value,
              list.iter().collect(),
              depth,
              max_depth,
              &mut active,
              &mut tasks,
            )?;
            continue;
          }

          if let Ok(tuple) = value.cast::<PyTuple>() {
            Self::start_sequence(
              &value,
              tuple.iter().collect(),
              depth,
              max_depth,
              &mut active,
              &mut tasks,
            )?;
            continue;
          }

          let scalar = Self::from_scalar(&value)?;
          if let Self::String(text) = &scalar {
            nested_css |= crate::stack::nested_css(text);
          }
          values.push(scalar);
        }
        Task::FinishSequence {
          identity,
          item_count,
        } => {
          active.remove(&identity);
          let start = values
            .len()
            .checked_sub(item_count)
            .expect("sequence result count");
          let items = values.split_off(start);
          values.push(Self::Seq(SequenceValues(items)));
        }
        Task::FinishMapping {
          identity,
          entry_count,
        } => {
          active.remove(&identity);
          let item_count = entry_count.checked_mul(2).expect("mapping result count");
          let start = values
            .len()
            .checked_sub(item_count)
            .expect("mapping result count");
          let mut items = values.split_off(start).into_iter();
          let mut entries = Vec::with_capacity(entry_count);
          for _ in 0..entry_count {
            let key = items.next().expect("mapping key");
            let value = items.next().expect("mapping value");
            entries.push((key, value));
          }
          debug_assert!(items.next().is_none());
          values.push(Self::Map(MappingEntries(entries)));
        }
      }
    }

    Ok(Snapshot {
      value: values.pop().expect("root value"),
      deepest,
      nested_css,
    })
  }

  fn start_sequence<'py>(
    container: &Bound<'py, PyAny>,
    items: Vec<Bound<'py, PyAny>>,
    depth: usize,
    max_depth: usize,
    active: &mut HashSet<usize>,
    tasks: &mut Vec<Task<'py>>,
  ) -> PyResult<()> {
    let identity = Self::enter_container(container, depth, max_depth, active)?;
    tasks.push(Task::FinishSequence {
      identity,
      item_count: items.len(),
    });
    for item in items.into_iter().rev() {
      tasks.push(Task::Visit {
        value: item,
        depth: depth + 1,
      });
    }
    Ok(())
  }

  fn enter_container(
    value: &Bound<'_, PyAny>,
    depth: usize,
    max_depth: usize,
    active: &mut HashSet<usize>,
  ) -> PyResult<usize> {
    if depth >= max_depth {
      return Err(PyValueError::new_err(format!(
        "node input nests deeper than {max_depth} levels"
      )));
    }

    let identity = value.as_ptr() as usize;
    if !active.insert(identity) {
      return Err(PyValueError::new_err("node input contains a cycle"));
    }
    Ok(identity)
  }

  fn from_scalar(value: &Bound<'_, PyAny>) -> PyResult<Self> {
    if value.is_none() {
      return Ok(Self::Null);
    }

    if let Ok(bytes) = value.cast::<PyBytes>() {
      return Ok(Self::Bytes(bytes.as_bytes().to_vec()));
    }

    if let Ok(bytearray) = value.cast::<PyByteArray>() {
      return Ok(Self::Bytes(bytearray.to_vec()));
    }

    if let Ok(memoryview) = value.cast::<PyMemoryView>() {
      let bytes = memoryview.call_method0("tobytes")?;
      return Ok(Self::Bytes(bytes.cast::<PyBytes>()?.as_bytes().to_vec()));
    }

    if let Ok(string) = value.cast::<PyString>() {
      return Ok(Self::String(string.extract()?));
    }

    if let Ok(boolean) = value.cast::<PyBool>() {
      return Ok(Self::Bool(boolean.is_true()));
    }

    if let Ok(integer) = value.cast::<PyInt>() {
      if let Ok(value) = integer.extract::<i64>() {
        return Ok(Self::I64(value));
      }
      return Ok(Self::U64(integer.extract()?));
    }

    if let Ok(float) = value.cast::<PyFloat>() {
      return Ok(Self::F64(float.value()));
    }

    Err(unsupported(value))
  }

  fn kind(&self) -> &'static str {
    match self {
      Self::Null => "None",
      Self::Bool(_) => "bool",
      Self::I64(_) | Self::U64(_) => "integer",
      Self::F64(_) => "float",
      Self::String(_) => "string",
      Self::Bytes(_) => "bytes",
      Self::Seq(_) => "sequence",
      Self::Map(_) => "mapping",
    }
  }
}

impl SequenceValues {
  fn is_empty(&self) -> bool {
    self.0.is_empty()
  }

  fn into_vec(mut self) -> Vec<Value> {
    mem::take(&mut self.0)
  }
}

impl IntoIterator for SequenceValues {
  type Item = Value;
  type IntoIter = std::vec::IntoIter<Value>;

  fn into_iter(self) -> Self::IntoIter {
    self.into_vec().into_iter()
  }
}

impl Drop for SequenceValues {
  fn drop(&mut self) {
    drop_value_tree(mem::take(&mut self.0));
  }
}

impl MappingEntries {
  fn entry_count(&self) -> usize {
    self.0.len()
  }

  fn into_vec(mut self) -> Vec<(Value, Value)> {
    mem::take(&mut self.0)
  }
}

impl IntoIterator for MappingEntries {
  type Item = (Value, Value);
  type IntoIter = std::vec::IntoIter<(Value, Value)>;

  fn into_iter(self) -> Self::IntoIter {
    self.into_vec().into_iter()
  }
}

impl Drop for MappingEntries {
  fn drop(&mut self) {
    let entries = mem::take(&mut self.0);
    drop_value_tree(entries.into_iter().flat_map(|(key, value)| [key, value]));
  }
}

fn drop_value_tree(values: impl IntoIterator<Item = Value>) {
  let mut pending = values.into_iter().collect::<Vec<_>>();
  while let Some(mut value) = pending.pop() {
    match &mut value {
      Value::Seq(values) => pending.append(&mut values.0),
      Value::Map(entries) => {
        for (key, value) in mem::take(&mut entries.0) {
          pending.push(key);
          pending.push(value);
        }
      }
      Value::Null
      | Value::Bool(_)
      | Value::I64(_)
      | Value::U64(_)
      | Value::F64(_)
      | Value::String(_)
      | Value::Bytes(_) => {}
    }
  }
}

fn deserialize_value<T: DeserializeOwned>(value: Value) -> Result<T, String> {
  T::deserialize(value).map_err(|error| error.to_string())
}

fn unsupported(value: &Bound<'_, PyAny>) -> pyo3::PyErr {
  match value.get_type().name() {
    Ok(name) => PyValueError::new_err(format!("unsupported node input type {name:?}")),
    Err(_) => PyValueError::new_err("unsupported node input type"),
  }
}

fn invalid_type(expected: &str, value: &Value) -> Error {
  de::Error::custom(format!("expected {expected}, got {}", value.kind()))
}

impl<'de> Deserializer<'de> for Value {
  type Error = Error;

  fn deserialize_any<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::Null => visitor.visit_none(),
      Self::Bool(value) => visitor.visit_bool(value),
      Self::I64(value) => visitor.visit_i64(value),
      Self::U64(value) => visitor.visit_u64(value),
      Self::F64(value) => visitor.visit_f64(value),
      Self::String(value) => visitor.visit_string(value),
      Self::Bytes(value) => visitor.visit_byte_buf(value),
      Self::Seq(values) => visitor.visit_seq(Sequence {
        values: values.into_iter(),
      }),
      Self::Map(entries) => visitor.visit_map(Mapping {
        entries: entries.into_iter(),
        value: None,
      }),
    }
  }

  serde::forward_to_deserialize_any! {
    bool i8 i16 i32 i64 i128 u8 u16 u32 u64 u128 f32 f64
  }

  fn deserialize_char<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    let Self::String(value) = self else {
      return Err(invalid_type("one-character string", &self));
    };
    let mut chars = value.chars();
    let Some(character) = chars.next() else {
      return Err(de::Error::custom("expected a one-character string"));
    };
    if chars.next().is_some() {
      return Err(de::Error::custom("expected a one-character string"));
    }
    visitor.visit_char(character)
  }

  fn deserialize_str<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    self.deserialize_string(visitor)
  }

  fn deserialize_string<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::String(value) => visitor.visit_string(value),
      value => Err(invalid_type("string", &value)),
    }
  }

  fn deserialize_bytes<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    self.deserialize_byte_buf(visitor)
  }

  fn deserialize_byte_buf<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::Bytes(value) => visitor.visit_byte_buf(value),
      Self::Seq(values) => visitor.visit_seq(Sequence {
        values: values.into_iter(),
      }),
      value => Err(invalid_type("bytes or integer sequence", &value)),
    }
  }

  fn deserialize_option<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::Null => visitor.visit_none(),
      value => visitor.visit_some(value),
    }
  }

  fn deserialize_unit<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::Null => visitor.visit_unit(),
      Self::Seq(values) if values.is_empty() => visitor.visit_unit(),
      value => Err(invalid_type("None or an empty sequence", &value)),
    }
  }

  fn deserialize_unit_struct<V: Visitor<'de>>(
    self,
    _name: &'static str,
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    self.deserialize_unit(visitor)
  }

  fn deserialize_newtype_struct<V: Visitor<'de>>(
    self,
    _name: &'static str,
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    visitor.visit_newtype_struct(self)
  }

  fn deserialize_seq<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    let values = match self {
      Self::Seq(values) => values.into_vec(),
      Self::Bytes(bytes) => bytes
        .into_iter()
        .map(|byte| Self::U64(byte.into()))
        .collect(),
      value => return Err(invalid_type("sequence", &value)),
    };
    visitor.visit_seq(Sequence {
      values: values.into_iter(),
    })
  }

  fn deserialize_tuple<V: Visitor<'de>>(
    self,
    _len: usize,
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    self.deserialize_seq(visitor)
  }

  fn deserialize_tuple_struct<V: Visitor<'de>>(
    self,
    _name: &'static str,
    _len: usize,
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    self.deserialize_seq(visitor)
  }

  fn deserialize_map<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    match self {
      Self::Map(entries) => visitor.visit_map(Mapping {
        entries: entries.into_iter(),
        value: None,
      }),
      value => Err(invalid_type("mapping", &value)),
    }
  }

  fn deserialize_struct<V: Visitor<'de>>(
    self,
    _name: &'static str,
    _fields: &'static [&'static str],
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    self.deserialize_map(visitor)
  }

  fn deserialize_enum<V: Visitor<'de>>(
    self,
    _name: &'static str,
    _variants: &'static [&'static str],
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    match self {
      Self::String(variant) => visitor.visit_enum(Enumeration {
        variant,
        value: None,
      }),
      Self::Map(entries) if entries.entry_count() == 1 => {
        let (variant, value) = entries
          .into_vec()
          .pop()
          .ok_or_else(|| de::Error::custom("empty enum"))?;
        let Self::String(variant) = variant else {
          return Err(de::Error::custom("enum variant must be a string"));
        };
        visitor.visit_enum(Enumeration {
          variant,
          value: Some(value),
        })
      }
      value => Err(de::Error::custom(format!(
        "expected enum string or single-entry mapping, got {}",
        value.kind()
      ))),
    }
  }

  fn deserialize_identifier<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    self.deserialize_string(visitor)
  }

  fn deserialize_ignored_any<V: Visitor<'de>>(self, visitor: V) -> Result<V::Value, Self::Error> {
    visitor.visit_unit()
  }
}

struct Sequence {
  values: std::vec::IntoIter<Value>,
}

impl<'de> SeqAccess<'de> for Sequence {
  type Error = Error;

  fn next_element_seed<T: de::DeserializeSeed<'de>>(
    &mut self,
    seed: T,
  ) -> Result<Option<T::Value>, Self::Error> {
    self
      .values
      .next()
      .map(|value| seed.deserialize(value))
      .transpose()
  }

  fn size_hint(&self) -> Option<usize> {
    Some(self.values.len())
  }
}

struct Mapping {
  entries: std::vec::IntoIter<(Value, Value)>,
  value: Option<Value>,
}

impl<'de> MapAccess<'de> for Mapping {
  type Error = Error;

  fn next_key_seed<K: de::DeserializeSeed<'de>>(
    &mut self,
    seed: K,
  ) -> Result<Option<K::Value>, Self::Error> {
    let Some((key, value)) = self.entries.next() else {
      return Ok(None);
    };
    self.value = Some(value);
    seed.deserialize(key).map(Some)
  }

  fn next_value_seed<V: de::DeserializeSeed<'de>>(
    &mut self,
    seed: V,
  ) -> Result<V::Value, Self::Error> {
    let value = self
      .value
      .take()
      .ok_or_else(|| de::Error::custom("map value requested before its key"))?;
    seed.deserialize(value)
  }

  fn size_hint(&self) -> Option<usize> {
    Some(self.entries.len())
  }
}

struct Enumeration {
  variant: String,
  value: Option<Value>,
}

impl<'de> EnumAccess<'de> for Enumeration {
  type Error = Error;
  type Variant = Variant;

  fn variant_seed<V: de::DeserializeSeed<'de>>(
    self,
    seed: V,
  ) -> Result<(V::Value, Self::Variant), Self::Error> {
    let variant = seed.deserialize(Value::String(self.variant))?;
    Ok((variant, Variant { value: self.value }))
  }
}

struct Variant {
  value: Option<Value>,
}

impl<'de> VariantAccess<'de> for Variant {
  type Error = Error;

  fn unit_variant(self) -> Result<(), Self::Error> {
    match self.value {
      None | Some(Value::Null) => Ok(()),
      Some(value) => Err(de::Error::custom(format!(
        "unit enum variant cannot contain {}",
        value.kind()
      ))),
    }
  }

  fn newtype_variant_seed<T: de::DeserializeSeed<'de>>(
    self,
    seed: T,
  ) -> Result<T::Value, Self::Error> {
    seed.deserialize(
      self
        .value
        .ok_or_else(|| de::Error::custom("newtype enum variant has no value"))?,
    )
  }

  fn tuple_variant<V: Visitor<'de>>(self, len: usize, visitor: V) -> Result<V::Value, Self::Error> {
    self
      .value
      .ok_or_else(|| de::Error::custom("tuple enum variant has no value"))?
      .deserialize_tuple(len, visitor)
  }

  fn struct_variant<V: Visitor<'de>>(
    self,
    fields: &'static [&'static str],
    visitor: V,
  ) -> Result<V::Value, Self::Error> {
    self
      .value
      .ok_or_else(|| de::Error::custom("struct enum variant has no value"))?
      .deserialize_struct("", fields, visitor)
  }
}

impl fmt::Display for Value {
  fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
    formatter.write_str(self.kind())
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use pyo3::{
    Python,
    types::{PyDict, PyList},
  };

  #[test]
  fn mappings_and_sequences_keep_python_order() {
    Python::attach(|py| {
      let mapping = PyDict::new(py);
      mapping.set_item("third", 3).unwrap();
      mapping.set_item("first", 1).unwrap();
      mapping.set_item("second", 2).unwrap();

      let Snapshot { value, .. } = Value::from_pyobject(mapping.as_any(), 32).unwrap();
      let Value::Map(entries) = value else {
        panic!("expected mapping");
      };
      let keys: Vec<_> = entries
        .into_iter()
        .map(|(key, _)| match key {
          Value::String(key) => key,
          other => panic!("expected string key, got {other:?}"),
        })
        .collect();
      assert_eq!(keys, ["third", "first", "second"]);

      let sequence = PyList::new(py, [3, 1, 2]).unwrap();
      let Snapshot { value, .. } = Value::from_pyobject(sequence.as_any(), 32).unwrap();
      let Value::Seq(values) = value else {
        panic!("expected sequence");
      };
      let numbers: Vec<_> = values
        .into_iter()
        .map(|value| match value {
          Value::I64(value) => value,
          other => panic!("expected integer, got {other:?}"),
        })
        .collect();
      assert_eq!(numbers, [3, 1, 2]);
    });
  }

  #[test]
  fn repeated_sibling_sequences_are_not_false_cycles() {
    Python::attach(|py| {
      let shared = PyList::new(py, [1]).unwrap();
      let root = PyList::new(py, [] as [i64; 0]).unwrap();
      root.append(shared.clone()).unwrap();
      root.append(shared).unwrap();

      let Snapshot { value, .. } = Value::from_pyobject(root.as_any(), 32).unwrap();
      let Value::Seq(values) = value else {
        panic!("expected sequence");
      };
      assert_eq!(values.into_vec().len(), 2);
    });
  }

  #[test]
  fn deeply_nested_values_drop_iteratively() {
    let mut value = Value::Null;
    for _ in 0..20_000 {
      value = Value::Seq(SequenceValues(vec![value]));
    }
    drop(value);
  }
}
