# Choose applicable profiles

Every repo follows the baseline. Combine one or more language profiles with every relevant product profile; a Python API with a React client and Terraform needs Python, TypeScript, service, web and infrastructure rules.

| Profile | Apply to |
| --- | --- |
| [Python](python.md) | Python packages, apps, automation and scripts |
| [JavaScript/TypeScript](typescript.md) | Browser and Node projects |
| [Other languages](other-languages.md) | Go, Rust, JVM, .NET, native and other ecosystems |
| [Web/UI](web.md) | Websites and interfaces, including internal tools |
| [Services/APIs](services.md) | Servers, APIs, workers and event-driven systems |
| [Libraries](libraries.md) | Distributed packages, SDKs and reusable components |
| [CLIs/automation](cli.md) | Command-line tools and unattended scripts |
| [Data/ML](data-ml.md) | ETL, notebooks, analytics, model training and inference |
| [Infrastructure](infrastructure.md) | IaC, containers, platform and deployment configuration |
| [Mobile/desktop](mobile-desktop.md) | Installed native, hybrid and desktop applications |

Manifest profile names: `python`, `typescript`, `other-languages`, `web`, `services`, `libraries`, `cli`, `data-ml`, `infrastructure`, `mobile-desktop`. The auditor validates profile selection and Python/TypeScript structural prerequisites only. Product-specific behavior needs human review and appropriate tests.
