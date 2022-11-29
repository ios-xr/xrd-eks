# Prerequisites

Prerequisites described in [the project README](../README.md) must be met
before running the tests.

# Running the tests

Use [`nox`](https://nox.thea.codes/en/stable/) to run the tests in an isolated
virtual environment.  Positional arguments are passed to pytest; in particular
`--region` must be specified, and at least one of `--control-plane-repository`
or `--vrouter-repository` must be specified for any tests to run.

For each tag passed in `--control-plane-tags` and `--vrouter-tags`, it is
assumed there is an image with this tag in `--control-plane-repository` and
`--vrouter-repository` respectively.

For example, to run both `xrd-control-plane` and `xrd-vrouter` tests, on both
7.7.1 and latest images:

```
nox --                                                         \
    --region $REGION                                           \
    --control-plane-repository $REGISTRY/xrd/xrd-control-plane \
    --vrouter-repository $REGISTRY/xrd/xrd-vrouter             \
    --control-plane-tags 7.7.1 latest                          \
    --vrouter-tags 7.7.1 latest
```

Alternatively if you prefer to (re)use your own virtual environment, install
`requirements.txt` and use `pytest`:

```
pip install -r requirements.txt
pytest
```
