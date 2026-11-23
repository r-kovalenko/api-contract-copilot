# Dependency maintenance

Update dependencies for high or critical vulnerabilities, or an explicit feature/compatibility need, rather than for every release. Prefer the smallest supported patched upgrade and avoid unrelated lockfile refreshes. A major upgrade may be necessary when it is the only supported remediation; review its migration impact and run the required checks.

## Repository configuration

`.github/dependabot.yml` sets `open-pull-requests-limit: 0` for GitHub Actions, backend Python, frontend npm, and Python security tooling. This stops routine version-update PRs once merged into the default branch. The required weekly schedule does not turn routine updates back on. Security updates are grouped within each ecosystem/directory and remain eligible independently of that limit. Existing PRs are not evidence of new policy violations; review them individually.

This file cannot select vulnerability severity. Configure the following GitHub rule separately.

## GitHub severity rule

In repository **Settings > Advanced Security**:

1. Keep **Dependabot alerts** enabled so all severities remain visible.
2. Under **Dependabot rules**, create an enabled custom rule named **High and critical security fixes**.
3. Select severity **High** and **Critical**, with action **Open a pull request**. Do not add a production-only filter: development dependencies are in scope too.
4. Disable the general **Dependabot security updates** setting, as required for the selective rule's PR action, and save the rule. Complete both settings together; disabling the general setting without an active rule leaves automatic remediation unavailable.
5. Verify the saved rule is enabled and matches only the intended severities. Inspect rule insights and the next eligible alert/PR to verify operation. Other rules must not open PRs for lower severities.

Verification on 2026-11-23: the GitHub API reports general automated security updates disabled. The custom rule's saved criteria and enabled state have **not been verified**. Do not consider high/critical automatic remediation active until that verification is complete. The configuration PR alone cannot activate this rule.

Low/moderate alerts remain available for manual exposure review; do not auto-dismiss them. If no patched version exists, track the advisory and mitigation rather than opening unrelated upgrade PRs. Updates are never auto-merged by this policy.

## CI remains authoritative

PR tests, CodeQL, secret scanning, and dependency audits remain enabled. Python audits currently fail on any known advisory, while frontend audits block high/critical findings subject to the existing narrowly scoped, expiring exception in [the security baseline](security.md). The automatic PR threshold does not change those gates: a lower-severity Python finding still requires triage and remediation to pass CI.

## GitHub references

- [Customizing Dependabot security PRs](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/customizing-dependabot-security-prs)
- [Configuring auto-triage rules](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/auto-triage-dependabot-alerts)
- [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
