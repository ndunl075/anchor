# Provider plugins

Third-party providers register an implementation of Anchor's provider protocol under the
anchor.providers entry-point group:

~~~toml
[project.entry-points."anchor.providers"]
my_provider = "my_anchor_provider:Provider"
~~~

The class must expose name, version, supports(feature), and an async
generate(Request) -> Response method. Return a Response(error=...) for terminal failures;
never raise provider failures into the runner. The adapter receives already-normalized messages and
must not grade, print, or implement retry policy.
