# OSINT Collector

This module provides a Trigger that is able to regularily fetch sources of data
to generate observables.

It supports the following `global_format`s:

* `line`
* `html`
* `regex`
* `json`
* `csv`

All formats require the `fields` configuration value specifying the output fields
to generate and from which token. Use `_` to ignore a token.

## Line Configuration Options

* `ignore` (optional): ignore all lines starting with these strings (separated by spaces)
* `separator` (optional): split lines into tokens using this separator (space by default)

## CSV Configuration Options

* `ignore` (optional): ignore all lines starting with these strings (separated by spaces)
* `separator` (optional): split lines into tokens using this separator (',' by default)
* `quotechar` (optional): Character used to quote elements in the CSV content ('"' by default)

## HTML Configuration Options

* `iterate_over` (optional): select a table using a css class (starting with `.`) or ID (starting with `#`)

## Regex Configuration Options

* `ignore` (optional): ignore all lines starting with these strings (separated by spaces)
* `item_format`: list with only one regex to use with a group for each generated token

## JSON Configuration Options

* `iterate_over` (optional): JSONPath expression to evaluate to get the list of items to process
* `item_format`: list of JSONPath expression to evaluate

When the JSONPath expression will return a list of values and you want one observable created for
each value, you can add a `*` before the field name.

For example, if you have a dataset with the following format:

```
{
    "items": [
        {
            "ips": [...]
        },
        {
            "ips": [...]
        }
    ]
}
```

You could use the following configuration:

```
{
    "fields": ["*ipv4-addr"],
    "iterate_over": "$.items",
    "item_format": ["$.ips"]
}
```
