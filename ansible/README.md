# Ansible tooling

## Callbacks

### HTML reports

#### Installation

Install required Python package `html` via PIP.

Copy the callback to `playbooks/callback_plugins/html_reports.py`.
Add it to your callbacks whitelist in `ansible.cfg`:

```
[...]
callback_whitelist      = timer, html_reports
[...]
```
