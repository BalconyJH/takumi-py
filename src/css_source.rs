//! Close each stylesheet at its own EOF before composing it with other sources.
//!
//! Takumi's list parser concatenates raw text. CSS EOF is meaningful: it closes
//! comments, strings and blocks and discards unfinished qualified-rule preludes.
//! Use the same CSS tokenizer to preserve those boundaries without inventing a
//! second selector/declaration parser. Takumi still owns all CSS semantics.

use cssparser::{
  AtRuleParser, CowRcStr, ParseError, Parser, ParserState, QualifiedRuleParser, StyleSheetParser,
  ToCss, Token, TokenSerializationType, serialize_identifier,
};

pub(crate) fn closed_stylesheet(css: &str) -> String {
  let mut input = Parser::new(css);
  let mut rules = ClosedRules;
  let mut output = String::with_capacity(css.len());
  for rule in StyleSheetParser::new(&mut input, &mut rules).flatten() {
    output.push_str(&rule);
    output.push('\n');
  }
  output
}

/// A serialized declaration may contain raw custom-property / deferred values.
/// Keep those values inside one declaration even when they came from a Python
/// mapping rather than the CSS parser. The caller supplies the final semicolon.
pub(crate) fn closed_declaration(css: &str) -> Result<String, ()> {
  let mut input = Parser::new(css);
  let name = input.expect_ident_cloned().map_err(|_| ())?;
  input.expect_colon().map_err(|_| ())?;
  let mut output = String::new();
  serialize_identifier(&name, &mut output).map_err(|_| ())?;
  output.push(':');
  while let Ok(token) = input.next_including_whitespace_and_comments() {
    let token = token.clone();
    match token {
      Token::Semicolon => {
        input.expect_exhausted().map_err(|_| ())?;
        output.push(';');
        return Ok(output);
      }
      Token::CloseCurlyBracket
      | Token::CloseSquareBracket
      | Token::CloseParenthesis
      | Token::BadString(_)
      | Token::BadUrl(_) => return Err(()),
      _ => {}
    }
    token.to_css(&mut output).map_err(|_| ())?;
    let closing = match token {
      Token::Function(_) | Token::ParenthesisBlock => Some(')'),
      Token::SquareBracketBlock => Some(']'),
      Token::CurlyBracketBlock => Some('}'),
      _ => None,
    };
    if let Some(closing) = closing {
      output.push_str(&input.parse_nested_block(closed_tokens).map_err(|_| ())?);
      output.push(closing);
    }
  }
  // A missing terminator can mean a raw comment/string swallowed it. Treat that
  // as an invalid structured declaration instead of affecting the next one.
  Err(())
}

struct ClosedRules;

impl<'i> QualifiedRuleParser<'i> for ClosedRules {
  type Prelude = String;
  type QualifiedRule = String;
  type Error = ();

  fn parse_prelude(&mut self, input: &mut Parser<'i>) -> Result<String, ParseError<()>> {
    closed_tokens(input)
  }

  fn parse_block(
    &mut self,
    prelude: String,
    _start: &ParserState,
    input: &mut Parser<'i>,
  ) -> Result<String, ParseError<()>> {
    Ok(format!("{prelude}{{{}}}", closed_tokens(input)?))
  }
}

impl<'i> AtRuleParser<'i> for ClosedRules {
  type Prelude = String;
  type AtRule = String;
  type Error = ();

  fn parse_prelude(
    &mut self,
    name: CowRcStr<'i>,
    input: &mut Parser<'i>,
  ) -> Result<String, ParseError<()>> {
    let mut prelude = String::from("@");
    serialize_identifier(&name, &mut prelude).map_err(|_| ParseError::custom(()))?;
    // A separator keeps an identifier at the start of the prelude from joining
    // the at-keyword when the original source used a comment between them.
    prelude.push(' ');
    prelude.push_str(&closed_tokens(input)?);
    Ok(prelude)
  }

  fn rule_without_block(&mut self, prelude: String, _start: &ParserState) -> Result<String, ()> {
    Ok(format!("{prelude};"))
  }

  fn parse_block(
    &mut self,
    prelude: String,
    _start: &ParserState,
    input: &mut Parser<'i>,
  ) -> Result<String, ParseError<()>> {
    Ok(format!("{prelude}{{{}}}", closed_tokens(input)?))
  }
}

/// CSS parser recursion is bounded by its native nested-block limit (75).
fn closed_tokens(input: &mut Parser<'_>) -> Result<String, ParseError<()>> {
  let mut output = String::new();
  let mut previous = TokenSerializationType::Nothing;
  while let Ok(token) = input.next_including_whitespace_and_comments() {
    let token = token.clone();
    let current = token.serialization_type();
    if previous.needs_separator_when_before(current) {
      output.push_str("/**/");
    }
    if matches!(token, Token::BadUrl(_)) {
      // A bad URL's raw contents can end in a backslash. Serializing that
      // content followed by `)` would escape the delimiter, and bad URLs consume
      // newlines until a real `)`, so the next stylesheet would be swallowed.
      // Keep `bad` unquoted to force a BadUrl token, then terminate it at the
      // unescaped `)` without retaining the unsafe trailing backslash.
      output.push_str("url(bad\")");
      previous = current;
      continue;
    }
    token
      .to_css(&mut output)
      .map_err(|_| ParseError::custom(()))?;
    let closing = match token {
      Token::Function(_) | Token::ParenthesisBlock => Some(')'),
      Token::SquareBracketBlock => Some(']'),
      Token::CurlyBracketBlock => Some('}'),
      // Keep a bad string invalid. Its missing closing quote must not consume
      // a serialized block terminator or the next stylesheet.
      Token::BadString(_) => {
        output.push('\n');
        None
      }
      _ => None,
    };
    if let Some(closing) = closing {
      output.push_str(&input.parse_nested_block(closed_tokens)?);
      output.push(closing);
      previous = TokenSerializationType::Nothing;
    } else {
      previous = current;
    }
  }
  Ok(output)
}
