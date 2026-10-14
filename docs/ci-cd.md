# Continuous integration and delivery

Every repository runs GitHub Actions on pull requests and pushes to `main`, and supports manual validation. CI requires no external API keys. Python 3.12 and Node.js 24 are the baseline runtimes.

## Checks and artifacts

Python: install locked dependencies, run Ruff lint and format checks, run pytest with coverage and JUnit output. Main frontend: `npm ci`, TypeScript checks, Vitest, and a production build. Containers: build each Dockerfile and check its HTTP endpoint. The final `CI` status fails if any prerequisite fails or is cancelled/skipped.

Python coverage and JUnit results are saved as Actions artifacts. Coverage is reported without an artificial starter threshold; broader tests and a meaningful threshold belong to feature implementation.

## Delivery

A push to `main` publishes images only after the tests and each container's smoke check pass. Images use immutable commit-SHA tags:

- `ghcr.io/r-kovalenko/api-contract-copilot-backend:<sha>`
- `ghcr.io/r-kovalenko/api-contract-copilot-frontend:<sha>`
- `ghcr.io/r-kovalenko/api-provider-demo:<sha>`
- `ghcr.io/r-kovalenko/api-consumer-demo:<sha>`

Registry authentication uses the job-scoped GitHub token. Pull requests build and test but do not log in or publish. Newly created GHCR packages may be private even when the source repository is public; authenticate to pull them or explicitly change package visibility if public distribution is desired.

Container publication is continuous delivery, not deployment to a running server. No hosting service, production environment, billing resource, or deployment credential is configured. The deployment issue covers host selection, staging approval, database migrations, health checks, and rollback to a known image digest.

## Dependency updates

Use Python 3.12 to update locks from each Python project directory:

```sh
python -m pip install pip-tools
pip-compile --upgrade --output-file=requirements-runtime.txt pyproject.toml
pip-compile --upgrade --extra=dev --output-file=requirements-dev.txt pyproject.toml
```

Run the full checks after updates and commit the lock changes together. Frontend updates must include `package-lock.json`. Actions updates must retain full commit pins.

## Branch workflow

Work through pull requests and require the final `CI` check before merging. Squash merges keep history concise. The solo-owner workflow does not require a second person's review. A staging deployment will get its own protected GitHub environment once a host is selected.
