import sqlite3

import sqlite_vec


def make_db():
    """_summary_"""

    conn = sqlite3.connect(":memory:")
    # conn = sqlite3.connect("rag.db")

    conn.enable_load_extension(True)

    ###
    sqlite_vec.load(conn)

    conn.execute("""
    CREATE TABLE documents(
        id INTEGER PRIMARY KEY,
        text TEXT
    )
    """)

    conn.execute("""
    CREATE VIRTUAL TABLE vec_documents USING vec0(
        embedding FLOAT[384]
    )
    """)

    conn.enable_load_extension(False)
    ###

    (vec_version,) = conn.execute("select vec_version()").fetchone()
    print(f"vec_version={vec_version}")


# from langchain_community.tools.tavily_search import TavilySearchResults

# web_search_tool = TavilySearchResults(max_results=2)
