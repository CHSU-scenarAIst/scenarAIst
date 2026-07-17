# from langchain_tavily import TavilyExtract
from langchain_tavily import TavilySearch


def web_search() -> TavilySearch:
    """TODO"""
    return TavilySearch(
        max_results=1,
        topic="general",
        # include_answer=False,
        # include_raw_content=False,
        # include_images=False,
        # include_image_descriptions=False,
        # search_depth="basic",
        # time_range="day",
        # start_date=None,
        # end_date=None,
        # include_domains=None,
        # exclude_domains=None,
        # include_usage= False
    )


# def web_extract() -> TavilyExtract:
#     return TavilyExtract(
#         extract_depth="basic",
#         # include_images=False
#     )
