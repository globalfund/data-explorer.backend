# Data Explorer Backend

- [Data Explorer Backend](#data-explorer-backend)
  - [What is the Data Explorer Backend?](#what-is-the-data-explorer-backend)
  - [About the project](#about-the-project)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
  - [Development](#development)
    - [Commits](#commits)
    - [Code Management](#code-management)
    - [Adding packages](#adding-packages)
  - [Deployment](#deployment)
    - [Cron](#cron)
    - [Docker](#docker)

## What is the Data Explorer Backend?

The Data Explorer allows the exploration of data on investments and results in the fight against AIDS, tuberculosis and malaria around the world.

The Global Fund invests in smart, effective health programs to end AIDS, tuberculosis and malaria as epidemics. The Data Explorer visualizes where our investments come from, where they are and what they achieve by providing pledge and contribution data, grant financial data, and results data at global, regional and country levels.

We regularly improve and enhance the Data Explorer, and those updates are noted on the [Data Explorer Updates](https://www.theglobalfund.org/en/updates/) page on the Global Fund website. The data behind the Data Explorer and our API are available through the [Global Fund Data Service](https://data-service.theglobalfund.org/).

It makes use of [Data API Middleware](https://github.com/globalfund/data-explorer-server/) in order to retrieve all data needed for the visualisations/tables/filters and detail pages.

## About the project

- Website: [data.theglobalfund.org](https://data.theglobalfund.org)
- Authors: [Zimmerman](https://www.zimmerman.team/)
- Github Repo:
  - Frontend: [https://github.com/globalfund/data-explorer-client](https://github.com/globalfund/data-explorer-client)
  - Middleware: [https://github.com/globalfund/data-explorer-server](https://github.com/globalfund/data-explorer-server)

## Features

- Automated dataset updates via cron jobs.
- Dockerized deployment for easy setup and scalability.
- Dependency management with `uv` for reproducible environments.

## Prerequisites

- Python installed with `uv` for dependency management.
- Docker installed for containerized deployment.
- Bash shell for running setup scripts.

## Development

After installation, run: `uv sync` followed by `source .venv/bin/activate`.

Run the project with `uv run flask run`.

### Commits

[Commitlint](https://github.com/conventional-changelog/commitlint#what-is-commitlint) is used to check your commit messages.

When setting up the repository, after locally setting up an environment, ensure pre-commit is installed:

- Add pre-commit: `uv add pre-commit` or `pip install pre-commit`.
- Install pre-commit to git: `uv run pre-commit install` or `pre-commit install`.
- Install the commit hook to git: `uv run pre-commit install --hook-type commit-msg` or `pre-commit install --hook-type commit-msg`.

### Code Management

- *flake8* is used to maintain code quality in pep8 style
- *isort* is used to maintain the imports.
- *black* can be used to automatically format Python code to ensure consistency.
- *pre-commit* is used to enforce commit styles in the form:

```text
feat: A new feature
fix: A bug fix
docs: Documentation only changes
style: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
refactor: A code change that neither fixes a bug nor adds a feature
perf: A code change that improves performance
test: Adding missing or correcting existing tests
chore: Changes to the build process or auxiliary tools and libraries such as documentation generation
```

### Adding packages

After adding a package that needs to be included in `requirements.txt` for Docker, run:

```bash
uv export --no-dev --no-hashes --format requirements-txt > requirements.txt
```

## Deployment

### Cron

[scripts/setup_refresh_cron.sh](scripts/setup_refresh_cron.sh) contains an easy setup for the cron job that updates the datasets.

Run it with `sudo bash scripts/setup_refresh_cron.sh`.

### Docker

Ensure Docker is installed.

Run with `sudo docker compose up -d`

Rebuild with `sudo docker compose up --build`
