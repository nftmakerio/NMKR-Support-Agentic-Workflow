from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from crewai.tasks.task_output import TaskOutput
from nmkr_support_v4.tools.custom_tool import fetch_website_and_subpages
import logging
import sys
from io import StringIO
from typing import List
import json
from pathlib import Path

# Constants
GPT_MODEL = "gpt-4o"
#GPT_MODEL = "claude-3-5-sonnet-20240620"
LOG_FILE = 'app.log'

# Configure logging to write to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Custom handler to capture verbose output
class VerboseOutputHandler:
    def __init__(self):
        self.buffer = StringIO()

    def write(self, message):
        if message.strip():  # Avoid logging empty lines
            logger.info(f"Verbose Output: {message.strip()}")

    def flush(self):
        pass

# Redirect verbose output to logging
verbose_handler = VerboseOutputHandler()
sys.stdout = verbose_handler

# Get the directory where crew.py is located
CURRENT_DIR = Path(__file__).parent

# Load the JSON data from the first file
try:
    with open(CURRENT_DIR / 'links_with_descriptions.json', 'r') as file:
        links_data = json.load(file)
    logger.info("Successfully loaded links_with_descriptions.json")
except Exception as e:
    logger.error(f"Failed to load links_with_descriptions.json: {e}")
    raise

# Load the JSON data from the second file
try:
    with open(CURRENT_DIR / 'docs_links_with_descriptions.json', 'r') as file:
        docs_links_data = json.load(file)
    logger.info("Successfully loaded docs_links_with_descriptions.json")
except Exception as e:
    logger.error(f"Failed to load docs_links_with_descriptions.json: {e}")
    raise


class StructuredSupportRequest(BaseModel):
    """
    Represents a structured support request with boolean flags for business, technical, and user categories.
    """
    business: bool
    technical: bool
    user: bool
    content: str

class RelevantLinks(BaseModel):
    """
    Represents a structured output of relevant links for a support request.
    """
    business: List[str]
    user: List[str]
    technical: List[str]

def check_category(output: TaskOutput, category: str) -> bool:
    """
    Checks if the given category is present in the task output.
    """
    try:
        if not output or not hasattr(output, 'raw_output'):
            logger.warning(f"No output or raw_output attribute found for {category} check.")
            return False
        structured_data = output.raw_output
        if isinstance(structured_data, StructuredSupportRequest):
            return getattr(structured_data, category, False)
        if isinstance(structured_data, str):
            return category in structured_data.lower()
        return False
    except Exception as e:
        logger.error(f"Error in {category} condition: {e}")
        return False

def is_user(output: TaskOutput) -> bool:
    return check_category(output, 'user')

def is_business(output: TaskOutput) -> bool:
    return check_category(output, 'business')

def is_technical(output: TaskOutput) -> bool:
    return check_category(output, 'technical')

def validate_support_request(support_request: str) -> bool:
    """
    Validates the support request input.
    """
    if not support_request or not isinstance(support_request, str):
        logger.error("Invalid support request: empty or not a string.")
        return False
    logger.info("Support request validated successfully.")
    return True

# Define agents
routing_agent = Agent(
    role="Senior NMKR Support Routing Specialist",
    goal="Identify and provide the most relevant links from NMKR's website and documentation to assist in resolving the user's support request.",
    backstory="With a deep knowledge of NMKR's online resources, you are adept at pinpointing the exact links that will provide the necessary information to address user inquiries effectively.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL
)

structuring_support_request_agent = Agent(
    role="Senior NMKR Support Input Specialist",
    goal="Transform user support requests into a structured format that clearly outlines the key components and requirements for further processing.",
    backstory="Your expertise lies in dissecting and organizing user inquiries into a clear, actionable format, ensuring that all subsequent agents can easily understand and address the user's needs.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL
)

link_provider_agent = Agent(
    role="NMKR Resource Link Specialist",
    goal="Identify and provide the most relevant links from NMKR's website and documentation to assist in resolving the user's support request.",
    backstory="With a deep knowledge of NMKR's online resources, you are adept at pinpointing the exact links that will provide the necessary information to address user inquiries effectively.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL
)

business_development_agent = Agent(
    role="NMKR Business Development Specialist",
    goal="Deliver comprehensive business-related information, including pricing, partnerships, and strategic insights, to address user inquiries.",
    backstory="Your extensive understanding of NMKR's business model and market positioning allows you to provide detailed and accurate business-related information to users.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL,
    tools=[fetch_website_and_subpages]
)

user_support_agent = Agent(
    role="NMKR User Support Specialist",
    goal="Offer user-focused guidance and solutions, including how-to information, troubleshooting, and best practices for using NMKR's services.",
    backstory="With a strong background in user support, you are skilled at providing clear, step-by-step assistance to help users navigate and utilize NMKR's offerings effectively.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL,
    tools=[fetch_website_and_subpages]
)

technical_support_agent = Agent(
    role="NMKR Technical Support Specialist",
    goal="Provide in-depth technical information and solutions, including API functionality, Studio features, and technical troubleshooting.",
    backstory="Your technical expertise in NMKR's products and services enables you to offer precise and actionable technical support to users.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL,
    tools=[fetch_website_and_subpages]
)

summary_agent = Agent(
    role="NMKR Support Summary Specialist",
    goal="Compile and present a concise, coherent summary of all responses and the original support request into a final, user-friendly answer.",
    backstory="With a knack for synthesizing information, you excel at creating clear and comprehensive summaries that encapsulate all aspects of the support process.",
    verbose=True,
    allow_delegation=False,
    llm=GPT_MODEL
)

# Define tasks
structuring_support_request_task = Task(
    description='Convert the users support request into a structured format that clearly identifies the key components and requirements for processing The user\'s request is: {support_request}.',
    expected_output='A well-organized, structured representation of the users support request.',
    agent=structuring_support_request_agent
)

routing_task = Task(
    description='''Analyze the structured support request and categorize it into business, technical, or user support questions. Ensure the categorization is accurate and comprehensive
        
    Return the categorization as a StructuredSupportRequest with boolean flags for each category.
    Include the output from the previous agent in the content field.''',
    expected_output='A StructuredSupportRequest object with precise boolean flags indicating the relevant categories.',
    agent=routing_agent,
    output_pydantic=StructuredSupportRequest,
    context=[structuring_support_request_task]  # Use the output of the structuring task
)

link_provider_task = Task(
    description='''Evaluate the user's support request and select the top 10 most relevant links from the provided data to assist in resolving the inquiry. The links available for selection are:
    {links_data}''',
    expected_output='A structured list of relevant links, categorized by type (business, user, technical).',
    agent=link_provider_agent,
    output_pydantic=RelevantLinks,
    context=[routing_task]
)

docs_link_provider_task = Task(
    description='''Evaluate the user's support request and select the top 10 most relevant links from the provided data to assist in resolving the inquiry. The links available for selection are:
    {docs_links_data}''',
    expected_output='A structured list of relevant links, categorized by type (business, user, technical).',
    agent=link_provider_agent,
    output_pydantic=RelevantLinks,
    context=[routing_task]
)

business_development_support_task = Task(
    description='''YOU ONLY EXECUTE THIS TASK IF THE USER'S REQUEST IS BUSINESS RELATED. OTHERWISE, SKIP THIS TASK.
    
    Review the structured support request and previous responses to add pertinent business-related information, such as pricing details and partnership opportunities.
    Use the fetch_website_and_subpages tool to check the links provided by the previous agent you deem to be relevant for providing the most accurate information.
 	''',
    expected_output='An enhanced response enriched with relevant business context and details.',
    agent=business_development_agent,
    condition=is_business,
    tools=[fetch_website_and_subpages],
    context=[routing_task, link_provider_task, docs_link_provider_task, ]  # Use the output of the link provider task
)

user_support_task = Task(
    description='''YOU ONLY EXECUTE THIS TASK IF THE USER'S REQUEST IS USER RELATED. OTHERWISE, SKIP THIS TASK.

    Examine the structured support request and previous responses to incorporate user-focused information, including how-to guides and troubleshooting tips.
    Use the fetch_website_and_subpages tool to check the links provided by the previous agent you deem to be relevant for providing the most accurate information.	''',
    expected_output='Enhanced response with user support context, including previous response.',
    agent=user_support_agent,
    condition=is_user,
    tools=[fetch_website_and_subpages],
    context=[routing_task, link_provider_task, docs_link_provider_task]  # Use the output of the link provider task
)

technical_support_task = Task(
    description='''YOU ONLY EXECUTE THIS TASK IF THE USER'S REQUEST IS TECHNICAL RELATED. OTHERWISE, SKIP THIS TASK.

    Analyze the structured support request and previous responses to include technical details, such as API functionality and Studio features.

    Use the fetch_website_and_subpages tool to check the links provided by the previous agent you deem to be relevant for providing the most accurate information.
    If the question is API or Code related, definitely check https://studio-api.nmkr.io/swagger/v2/swagger.json for the current Swagger API Documentation.''',
    expected_output='Enhanced response with technical context, including previous response.',
    agent=technical_support_agent,
    condition=is_technical,
    tools=[fetch_website_and_subpages],
    context=[routing_task, link_provider_task, docs_link_provider_task]  # Use the output of the link provider task
)

summary_task = Task(
    description='''Compile all previous responses and the original support request into a final. Make sure to include all the information you have gathered and to be as accurate as possible.
    ''',
    expected_output='A clear and concise final response that addresses the users support request comprehensively.',
    agent=summary_agent,
    context=[routing_task, business_development_support_task, user_support_task, technical_support_task]
)

docs_link_provider_task_second_run = Task(
    description='''Evaluate the summary provided by the previous agent and prepare a list of links that we can give the user so the user can continue the research on his own. Please use a maximum of 10 links.
    The links available for selection are:
    {docs_links_data}
    ''',
    expected_output='A structured list of relevant links, categorized by type (business, user, technical).',
    agent=link_provider_agent,
    output_pydantic=RelevantLinks, 
    context=[summary_task]
)


find_missing_information_task = Task(
    description='''Check the summary and determine if this is really answering the users support request. If not, find the missing information, using the links provided by the previous agentand querying them.

    Then take all the information you now have to create a user friendly response answering the users support request.
    Make sure to write it in a way that is easy to understand and follow and always be friendly. Include links for further reading for the user.
    ''',
    expected_output='A clear and concise final response that addresses the users support request comprehensively.',
    agent=summary_agent,
    tools=[fetch_website_and_subpages],
    context=[summary_task, docs_link_provider_task_second_run]
)

# Define crew
crew = Crew(
    agents=[
        structuring_support_request_agent,
        routing_agent,
        link_provider_agent,
        business_development_agent,
        user_support_agent,
        technical_support_agent
    ],
    tasks=[
        structuring_support_request_task,
        routing_task,
        link_provider_task,
        docs_link_provider_task,
        user_support_task,
        business_development_support_task,
        technical_support_task,
        summary_task,
        docs_link_provider_task_second_run,
        find_missing_information_task
    ],
    process=Process.sequential,
    verbose=True,
    planning=False,
    planning_llm=ChatOpenAI(model=GPT_MODEL)
)

# Remove the example usage code and move it to a separate function
def run_example():
    inputs = {
        'support_request': 'Hi! So I was wondering, how much does it cost to do an Airdrop with NMKR and how do I do it?',
        'links_data': links_data,
        'docs_links_data': docs_links_data
    }

    if validate_support_request(inputs['support_request']):
        logger.info("Starting crew workflow...")
        try:
            result = crew.kickoff(inputs=inputs)
            logger.info("Crew workflow completed successfully.")
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Error during crew workflow: {e}")
    else:
        logger.error("Support request validation failed.")

if __name__ == "__main__":
    run_example()