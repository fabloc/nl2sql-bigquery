# Application to translate Natural Language to Bigquery SQL Query

## Google Disclaimer

This is not an officially supported Google Product

## Introduction

BigQuery is the platform of choice for many companies to store and analyze their data. It leverages SQL as high-level interaction language. Althought very common among data architects, some use-cases require end-user without technical knowledge to be able to perform queries on the data warehouse. An example is a marketing persona which uses the platform to explore the data and create customer segmentations. This persona will be more easily convinced to use a platform based on BigQuery if the interface does not require SQL knowledge, or proprietary custom language on top of BigQuery.

This project aims at providing an abstraction layer on top of BigQuery, offering natural language as the interface. The application then leverages state-of-the-art LLM models in order to convert the question to a BigQuery SQL query.

Several nl2sql approaches exists to achieve this, however there is no guarantee that the generated query actually matches the user's request. This can be problematic for complex tables, and a major blocker for the widespread adoption of such a solution. User's confidence in the result matching their initial request is paramount.

This application provides a reliable mechanism, leveraging a validation feedback loop, ensuring that the generated SQL Query is matching the user's intent.

Another complexity pertaining to BigQuery is the impossibility to predict costs, as queries are charged based on the amount of data scanned (for on-demand queries), and end-users may have unpredictable query behaviours, leading to undeterministic costs on BigQuery. Some solutions exists, and in particular for a complete end-to-end solution demonstrating the performance of this solution on complex and large data tables, please refer to the repository [`genai-powered-cdp`](https://github.com/fabloc/genai-powered-cdp) which simulates a Customer Data Platform by deploying events/users/products tables, with associated aggregated tables.


## Architecture

This application implements the following workflow:

![Technical Architecture](images/nl2sql-architecture.png "NL2SQL Chat App Archteicture")

To achieve this, the demo uses the following technologies:

Deployment:
- Cloud Build
- Artifact Registry

Execution:
- Cloud Run
- Vertex AI (Gemini Pro and Unicorn models)
- BigQuery
- Cloud SQL for PosgreSQL with pgvector extension

Application Stack
- UI/Front-end: Streamlit Framework
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


# Technical Deep-Dive

The application needs to be initialized with tables schemas. This is done automatically by providing the project_id, dataset_id, and optionally the table list inside the dataset (if none is provided, all tables in the dataset are considered for matching). The schemas are then converted to embeddings using the 'gecko-embedding' model (can be changed in the configuration file) and stored in the Vector Database in the 'table-embeddings' table.

Optionnally, samples questions/queries can be provided in yaml format. The process is the same: the question are converted to embeddings, and stored in the Vector Database alongside the valid SQL Query in the 'sql-embeddings' table.

When processing a user request, the following steps are executed:

1. application first tries to match the question exactly with a question stored in the Vector database. If there is a match, then the associated valid SQL Query is retrieved from the Vector DB and used as the final SQL Query.
2. If no match is found, then the application will try to find similar questions in Vector Database. If matches are found, they are injected in the LLM prompt, along with the associated SQL Query (few-shot prompt).
3. If similar questions have been found, Gemini Pro is used to execute the prompt. Gemini Pro is very good at identifying patterns in samples data, and excels at few-shot. It is also very quick to generate a result. On the other hand, if no similar question was dound then 'unicorn' model is used to execute the prompt. It is larger than Gemini, slower, but much more efficient at following complex rules in the prompt in 0-shot.
4. Once a SQL Query is generated, the validation feedback loop kicks in: 2 processes are executed in parallel: A dry-run of the SQL Query using BigQuery to validate the SQL Syntax, and a prompt using 'unicorn' model to validate that the generated SQL Query matches the initial user's intent. If an error is found in either the BigQuery dry-run or the LLM semantics validation, go back to step 3, and generate a new prompt, also injecting the errors identified, and previous errors as well.
5. If the validations were successful, the final SQL Query is executed against BigQuery and the results are displayed to the user. This behaviour can be changed in the configuration file.
6. The question and associated generated query are added to the Vector database for future matching.


# Configuration

## Required Properties

The following properties are required to deploy and run the application.
They can be set in the setup file located at [`/installation_scripts/setup.sh`](/installation_scripts/setup.sh).

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="PROJECT_ID"></a> [project\_id](#input\_project_id) | Project id where to deploy the application infrastrcture | `string` | `nl2sql-demo-project` | yes |
| <a name="REGION"></a> [region](#input\_region) | Region where to deploy the application infrastructure | `string` | `europe-west1` | yes |
| <a name="AUTH_USER"></a> [auth\_user](#input\_auth\_user) | User identity | `string` | `nl2sql_user` | yes |
| <a name="ARTIFACT_REGISTRY_REPO"></a> [artifact\_registry\_repo](#input\_artifact\_registry\_repo) | Name of the Artifact Registry Repository used to store the Docker image generated during the setup phase and used to deploy Cloud Run instances | `string` | `nl2sql-repo` | yes |
| <a name="SERVICE_NAME"></a> [service\_name](#input\_service\_name) | Name of the Cloud Run service to deploy | `string` | `nl2sql-service` | yes |
| <a name="DATABASE_NAME"></a> [database\_name](#input\_database\_name) | Name of the database to deply | `string` | `nl2sql-rag-db` | yes |
| <a name="DATABASE_USER"></a> [database\_user](#input\_database\_user) | User name for the Vector Database | `string` | `nl2sql-admin` | yes |
| <a name="DATABASE_PASSWORD"></a> [database\_password](#input\_database\_password) | Password associated with the Database User above | `string` | `>rJFj8HbN<:ObiEm` | yes |
| <a name="BIGQUERY_DATASET"></a> [bigquery\_dataset](#input\_bigquery\_dataset) | Name of the BigQuery dataset to use | `string` | `cdp_demo` | yes |

## Optional Properties

The following properties are optional.

### Tables Selection

If the specified dataset contains many tables and only a subset must be used for the SQL Query generation, set the `BIGUERY_TABLES` property in the file `setup.sh`. It should have the format `["table1", "table2", etc.]`

### Sample Questions/SQL Queries

In the folder `config/query_samples`, files can be added to bootstrap the Vector Database with pairs of Question/SQL Queries curated by the data architects. This is useful for complex tables where description is not always sufficient to enable LLM models to generate appropriate queries.

The structure is the following:

Name of the file: The name should match exactly the name of the table for which the samples apply with suffix '.yaml'. For example, for table `users_table`, the query sample file should be named `users_table.yaml` inside the folder config/queries_samples

Content of the file: The body of the file should be YAML formatted. Each sample should have the following structure:

```
- Question: What are the top 5 products purchased in the last 3 months?
  SQL Query: |-
    SELECT
      product_name,
      SUM(daily_product_purchased_items) AS total_purchased_items
    FROM
      `{{ project_id }}.{{ dataset_id }}.product_aggregates`
    WHERE
      DATE(session_day) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
    GROUP BY
      product_name
    ORDER BY
      total_purchased_items DESC
    LIMIT 5
```

The sample accepts 2 placeholders that will be automatically replaced by the appropriate values during the application deployment:
{{ project_id }} and {{ dataset_id }}.


# Tables Descriptions

Tables description are important in the overall relevancy of the generated SQL Queries. Every columns should have a `description` field. This description is added in the schema generated for each table and used as part of the LLM prompt.

# Future Improvements

 - `AUTH_USER` variable is hardcoded and used to identify the user making the request. User log in should be implemented, and actual user identity should be used to track the user's activity.
 - Display the query that the feedback loop inferred from the generated query so that the end-user can validate that it actually matches his intent. Allow the user to vote up or down (if vote up, the generated query is added to the Vector Database)


# Getting help

If you have any questions or if you found any problems with this repository, please report through GitHub issues.
