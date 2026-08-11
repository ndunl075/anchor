# CI usage

Anchor exits with code 2 when a comparison finds regressions, so an existing CI system can fail
without a wrapper script.

~~~yaml
- name: Evaluate candidate model
  run: |
    pip install anchor-eval
    anchor run --model claude-opus-5 --name candidate
    anchor compare @baseline @latest
~~~

Provide the model API key through your CI secret configuration. Commit .anchor/runs/ for a durable
audit trail. Never commit .anchor/cache/.
