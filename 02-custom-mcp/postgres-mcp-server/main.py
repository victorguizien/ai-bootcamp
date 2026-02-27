import psycopg2
from dotenv import load_dotenv, find_dotenv
import os
from mcp.server.fastmcp import FastMCP

load_dotenv(find_dotenv())

mcp = FastMCP('postgres-mcp-server')

DB_CONFIG = {
    "host": os.getenv("host"),
    "port": os.getenv("port"),
    "database": os.getenv("database"),
    "user": os.getenv("username"),
    "password": os.getenv("password"),
}

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

@mcp.tool()
async def find_schemas():
    """Find all schemas in the database"""
    sql = """
    SELECT schema_name FROM information_schema.schemata
    """
    cursor.execute(sql)
    return cursor.fetchall()


@mcp.tool()
async def find_tables(schema: str):
    """Find all tables in a schema"""
    sql = """
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = %s
    """
    cursor.execute(sql, (schema,))
    return cursor.fetchall()


@mcp.tool()
async def describe_table(schema: str, table: str):
    """Describe a table"""
    sql = """
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s
    """
    cursor.execute(sql, (schema, table))
    return cursor.fetchall()

@mcp.tool()
async def execute_sql(sql: str):
    """Execute a SQL query"""
    cursor.execute(sql)
    return cursor.fetchall()


def main():
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()