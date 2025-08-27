import os
import aiomysql
# Variables de entorno

#Base de datos para el historial de chat
MYSQL_HOST = os.environ.get('Db_HOST')
MYSQL_USER = os.environ.get('Db_USER')
MYSQL_PASSWORD = os.environ.get('Db_PASSWORD')
MYSQL_DB = os.environ.get('Db_NAME')
MYSQL_PORT = int(os.environ.get('Db_PORT', 3306))

# Base de datos para herramientas (Principal)
TOOLS_DB_HOST = os.environ.get('Main_Db_Host')
TOOLS_DB_USER = os.environ.get('Main_Db_User')
TOOLS_DB_PASSWORD = os.environ.get('Main_Db_password')
TOOLS_DB_NAME = os.environ.get('Main_Db')
TOOLS_DB_PORT = int(os.environ.get('Main_Db_Port', 3306))

REDISURL=os.environ.get('REDIS_URL')
REDISPASSWORD=os.environ.get('REDIS_PASSWORD')

#-------------------Pools-------------------#
async def create_mysql_pool():
    return await aiomysql.create_pool(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        autocommit=True
    )
    
async def create_tools_pool():
    return await aiomysql.create_pool(
        host=TOOLS_DB_HOST,
        user=TOOLS_DB_USER,
        password=TOOLS_DB_PASSWORD,
        db=TOOLS_DB_NAME,
        port=TOOLS_DB_PORT,
        autocommit=True
    )