import logging, cfg
import vertexai
from vertexai.preview.generative_models import GenerativeModel
from vertexai.preview.language_models import CodeGenerationModel, ChatModel, CodeChatModel, TextGenerationModel
import json, re
import jsonschema
from json import JSONDecodeError
from concurrent.futures import ThreadPoolExecutor

def init():

  vertexai.init(project=cfg.project_id, location="us-central1")

  # create logger
  global logger
  logger = logging.getLogger('nl2sql')

  global fast_sql_generation_model
  fast_sql_generation_model = createModel(cfg.fast_sql_generation_model)

  global fine_sql_generation_model
  fine_sql_generation_model = createModel(cfg.fine_sql_generation_model)

  global validation_model
  validation_model = createModel(cfg.validation_model_id)

  global sql_correction_model
  validation_model = createModel(cfg.sql_correction_model_id)

  global executor
  executor = ThreadPoolExecutor(5)

# Initialize Palm Models to be used
def createModel(model_id):

  if model_id == 'code-bison-32k':
    model = CodeGenerationModel.from_pretrained(model_id)
  elif 'gemini-pro' in model_id:
    model = GenerativeModel(model_id)
  elif model_id == 'codechat-bison-32k':
    model = CodeChatModel.from_pretrained(model_id)
  elif 'chat-bison-32k' in model_id:
    model = ChatModel.from_pretrained(model_id)
  elif model_id == 'text-unicorn':
    model = TextGenerationModel.from_pretrained('text-unicorn@001')
  else:
    logger.error("Requested model '" + model_id + "' not supported. Please review the config.ini file.")
    raise ValueError
  return model


def generate_sql(model, context_prompt, temperature = 0.0):
  if isinstance(model, GenerativeModel):
    generated_sql_json = model.generate_content(
      context_prompt,
      generation_config={
        "max_output_tokens": 1024,
        "temperature": temperature
    })
    generated_sql = generated_sql_json.candidates[0].content.parts[0].text
  elif isinstance(model, TextGenerationModel):
    generated_sql_json = model.predict(
      str(context_prompt),
      max_output_tokens = 1024,
      temperature = temperature
    )
    generated_sql = generated_sql_json.text
  return clean(generated_sql)

def question_to_query_examples(similar_questions):
  similar_questions_str = ''
  if len(similar_questions) > 0:
    similar_questions_str = "[Good SQL Examples]:\n"
    for similar_question in similar_questions:
      similar_questions_str += "- Question:\n" + similar_question['question'] + "\n-SQL Query:\n" + full_clean(similar_question['sql_query']) + '\n\n'
  return similar_questions_str


def gen_dyn_rag_sql(question,table_result_joined, similar_questions):

  similar_questions_str = question_to_query_examples(similar_questions)

  # If no similar question found, use more performant model to generate SQL Query (yet much slower)
  if fast := (len(similar_questions) > 0):
    logger.info("Similar question found, using fast model to generate SQL Query")
  else:
    logger.info("No similar question found, using fine model to generate SQL Query")

  context_prompt = f"""You are a BigQuery SQL guru. Write a SQL conformant query for Bigquery that answers the [Question] while using the provided context to correctly refer to the BigQuery tables and the needed column names.

[Guidelines]:
{cfg.prompt_guidelines}

[Table Schema]:
{table_result_joined}
{similar_questions_str}

[Question]:
{question}

[SQL Generated]:
"""

    #Column Descriptions:
    #{column_result_joined}

  logger.debug('LLM GEN SQL Prompt: \n' + context_prompt)

  context_query = generate_sql((fast_sql_generation_model if fast is True else fine_sql_generation_model), context_prompt)

  logger.info("SQL query generated:\n" + context_query)

  return full_clean(context_query)

def sql_explain(question, generated_sql, table_schema, similar_questions):

  logger.info("Starting SQL explanation...")

  response_json = {
    "question": "Write the question generated at step 2",
    "is_matching": "Return 'True' if the question generated at step 2 matches the [Question], 'False' otherwise",
    "mismatch_details": "Synthetic indications on how the SQL Query should be modified to answer the [Question]"
  }

  sql_explanation = {
    "reversed_question": "",
    "is_matching": True,
    "mismatch_details": ""
  }

  context_prompt = f"""You are an AI for SQL Analysis. Your mission is to analyse a SQL [SQL Query] and identify which question it answers to. Then you'll compare this question to the reference [Question].
You will reply only with a json object as described in the [Analysis Steps].

[Table Schema]:
{table_schema}

{question_to_query_examples(similar_questions)}[Analysis Steps]:
Let's work this out step by step to make sure we have the right answer:
1. Analyze the tables in [Table Schema], and understand the relations (column and table relations).
2. Analyze the [SQL Query] and find the question it answers. Ground the question generation with the [Table Schema] data only and make sure not to be influenced by the [Question].
3. Compare the question generated at step 2 to the [Question] and identify any semantic differences between the 2.
4. Answer using only the following json format: {json.dumps(response_json)}
5. Always use double quotes "" for json property names and values in the returned json object.
6. Remove ```json prefix and ``` suffix from the outputs. Don't add any comment around the returned json.

Remember that before you answer a question, you must check to see if it complies with your mission above.

[SQL Query]:
{generated_sql}

[Question]:
{question}

[Evaluation]:
"""

  logger.debug('Validation - Question Generation from SQL Prompt: \n' + context_prompt)

  try:

    raw_json = generate_sql(validation_model, context_prompt)
    logger.info("Validation completed with status: \n" + raw_json)
    validation_json = json.loads(raw_json, strict=False)

    # Analyze results for possible mismatch in SQL Query implementation
    sql_explanation['is_matching'] = True if validation_json['is_matching'] == 'True' else False
    sql_explanation["mismatch_details"] = validation_json['mismatch_details'] if ('mismatch_details' in validation_json) else ''

    sql_explanation["reversed_question"] = validation_json['question']

  except JSONDecodeError as e:
    logger.error("Error while deconding JSON response: " + str(e))
    sql_explanation['is_matching'] = 'False'
    sql_explanation['mismatch_details'] = 'Returned JSON malformed'
  except jsonschema.exceptions.ValidationError as e:
    logger.error("JSON Response does not match expected JSON schema: " + str(e))
    sql_explanation['is_matching'] = 'False'
    sql_explanation['mismatch_details'] = 'Returned JSON malformed'
  except jsonschema.exceptions.SchemaError as e:
    logger.error("Invalid JSON Schema !")
  except Exception as e:
    raise e

  logger.info("Validation response analysis: \n" + json.dumps(sql_explanation))

  return sql_explanation


class CorrectionSession:

  def __init__(self, table_schema: str, question: str, similar_questions: str):

    self.table_schema = table_schema
    self.question = question
    self.similar_questions = similar_questions
    
    self.model = createModel(cfg.sql_correction_model_id)
    self.iterations_history = []

  def add_iteration(self, sql, errors):
    self.iterations_history.append({
      'sql': sql.replace('\n', ' '),
      'errors': errors.replace('\n', '')
    })

  def format_history(self) -> str:
    history_str = ''
    for iteration in self.iterations_history:
      history_str += f"""{iteration['sql']}

"""
    return history_str
  
  def format_last_query(self) -> str:

    last_query = self.iterations_history[-1]
    return f"""SQL Query:
{last_query['sql']}

Errors:
{last_query['errors']}"""


  def get_corrected_sql(self, sql: str, bq_error_msg: str, validation_error_msg: str) -> str:
    logger.info("Sending prompt...")
    error_msg = ('- Syntax error returned from BigQuery: ' + bq_error_msg + '\n  ' if bq_error_msg != None else '') + ('- Semantics errors returned from SQL Validator: ' + validation_error_msg + '\n  ' if validation_error_msg != None else '')
    self.add_iteration(sql, error_msg)

    context_prompt = f"""You are a BigQuery SQL guru. This session is trying to troubleshoot a Google BigQuery SQL Query.
As the user provides the [Last Generated SQL Queries with Errors], return a correct [New Generated SQL Query] that fixes the errors.
It is important that the query still answers the original question and follows the following [Guidelines]:

[Guidelines]:
{cfg.prompt_guidelines}

[Table Schema]:
{self.table_schema}
{question_to_query_examples(self.similar_questions)}

[Correction Steps]:
Let's work this out step by step to make sure we have the right corrected SQL Query:
1. Analyze the tables in [Table Schema], and understand the relations (column and table relations).
2. Analyze the SQL Query in [Last Generated SQL Queries with Errors] and understand the associated syntax and semantic errors.
3. Propose a SQL Query that corrects the errors while answering the [Question].
4. The [New Generated SQL Query] must not be present in [Forbidden SQL Queries] 
5. Always use double quotes "" for json property names and values in the returned json object.
6. Remove ```json prefix and ``` suffix from the outputs. Don't add any comment around the returned json.

Remember that before you answer a question, you must check to see if it complies with your mission above.

[Question]:
{self.question}

[Last Generated SQL Queries with Errors]:
{self.format_last_query()}

[Forbidden SQL Queries]:
{self.format_history()}
[New Generated SQL Query]:
"""

    logger.debug('SQL Correction Prompt: \n' + context_prompt)

    response = generate_sql(self.model, context_prompt)
    logger.info("Received corrected SQL Query: \n" + response)

    return full_clean(response)


def full_clean(str):
  # Remove unwanted 'sql', 'json', and additional spaces
  return re.sub(' +', ' ', str.replace('\n', ' '))

def clean(str):
  return clean_json(clean_sql(str))

def clean_sql(result):
  result = result.replace("```", "").replace("```sql", "").removeprefix("sql")
  return result


def clean_json(result):
  result = result.replace("```", "").replace("```json", "").removeprefix("json")
  return result