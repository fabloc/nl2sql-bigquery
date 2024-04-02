# Application to translateNatural Language to Bigquery SQL Query

## Google Disclaimer

This is not an officially supported Google Product

## Introduction

BigQuery is the platform of choice for many companies to store and analyze their data. Some use-cases require end-user without technical knowledge to be able to perform queries on the data warehouse. An example is a marketing persona which uses the platform to explore the data and create customer segmentations. This persona will be more easily convinced to use a platform based on BigQuery if the interface does not require SQL knowledge, or proprietary custom language on top of BigQuery.
This project aims at providing an abstraction layer on top of BigQuery, offering a natural language interface to end users to build queries.
Several nl2sql approaches exists, but there is no guarantee that the generated query actually matches the user's request. This can be problematic for complex tables, and a major blocker for the adoption of such a solution. User's confidence in the result matching their initial request is paramount.
this repository aims at provided a reliable mechanism, with a validation feedback, ensuring that the generated SQL Query is as close as possible from the user's request.
For a complete end-to-end solution demonstrating the performance of this solution on complex and large data tables, please refer to the repository [`genai-powered-cdp`](https://github.com/fabloc/genai-powered-cdp) which simulates a Customer Data Platform by deploying events/users/products tables, with associated aggregated tables.


## Architecture

This application leverages Cloud Run for the application layer and streamlit for the UI. It implements the following workflow:
![Technical Architecture](images/nl2sql-architecture.png "NL2SQL Chat App Archteicture")

To achieve this, the demo uses the following technologies:

Demo deployment:
- Cloud Build
- Artifact Registry

Demo Execution:
- Cloud Run
- Vertex AI (Gemini Pro and Unicorn models)
- BigQuery
- Cloud SQL for PosgreSQL with pgvector extension
- Streamlit Framework
- Python 3.10


## Repository structure

```
.
├── app
└── config
    └── queries_samples
└── images
└── installation_scripts
    └── bigquery_dataset
    └── terraform
└── tools
```

- [`/app`](/app): Source code for demo app.  
- [`/config`](/config): Configuration files used by the application.
- [`/config/queries_samples`](/config/queries_samples): Sample questions with associated SQL queries that will be ingested inside the Vector Database during the provisioning of the resources.
- [`/images`](/images): Graphical assets used in the documentation pages.
- [`/installation_scripts`](/installation_scripts): Scripts used to install the application.
- [`/bigquery_dataset`](/installation_scripts/bigquery_dataset): Scripts used to import and generate the tables that will be used for the CDP demo.
- [`/installation_scripts/terraform`](/installation_scripts/terraform): Terraform files used to deploy the infrastructure for the demo.
- [`/tools`](/tools): Tools to be used to perform various maintenance tasks: debugging, cleaning the DB, etc.


# Environment Setup

Please follow the instructions detailed in the page [`/installation_scripts`](/installation_scripts) to set up the environment.


# Getting help

If you have any questions or if you found any problems with this repository, please report through GitHub issues.
