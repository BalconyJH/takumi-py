# Security policy

## Supported versions

Security fixes land in the newest release. While takumi-py is at 0.x, upgrade to the
latest minor version to receive them.

## Reporting a vulnerability

Report a vulnerability privately through
[GitHub private vulnerability reporting](https://github.com/BalconyJH/takumi-py/security/advisories/new),
not in a public issue. Include the takumi-py version, the platform, and the smallest
input that reproduces the problem. The discussion continues in the advisory.

takumi-py renders the nodes, HTML, CSS, fonts, and images it is given and never
fetches resources over the network, so crashes, hangs, or memory exhaustion caused by
untrusted input are in scope. Problems in Takumi itself are fixed upstream in
[kane50613/takumi](https://github.com/kane50613/takumi); report them here if you are
unsure where they belong.
