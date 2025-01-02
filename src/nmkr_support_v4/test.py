from crewai_tools import SpiderTool
from crewai import Agent, Crew, Process, Task
from crewai_tools import ScrapeWebsiteTool

def main():

# Initialize the tool with the website URL, 
# so the agent can only scrap the content of the specified website
    tool = ScrapeWebsiteTool(website_url='https://www.example.com')

    searcher = Agent(
        role="Web Research Expert",
        goal="Find related information from specific URL's",
        backstory="An expert web researcher that uses the web extremely well",
        tools=[tool],
        verbose=True,
    )

    return_metadata = Task(
        description="Scrape https://spider.cloud with a limit of 1 and enable metadata",
        expected_output="Metadata and 10 word summary of spider.cloud",
        agent=searcher
    )

    crew = Crew(
        agents=[searcher],
        tasks=[
            return_metadata,
        ],
        verbose=True
    )

    crew.kickoff()

if __name__ == "__main__":
    main()
