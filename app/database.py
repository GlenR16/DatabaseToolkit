import logging.config
import re
import pandas as pd
import logging
from datetime import datetime,timezone,timedelta
import random

from .models import Connection,Task, TaskHistory

CSV_SEPARATOR = "\x81"

def get_file_location(task_history: TaskHistory, folder: str, type: str):
    return f"media/{folder}/{task_history.pk}.{type}"

def set_logger_config(task: Task, task_history: TaskHistory):
    logger = logging.getLogger(f"{task.pk}_{task_history.pk}")
    log_filename = get_file_location(task_history,"logs","log")
    logging.basicConfig(filename=log_filename, level=logging.INFO,force=True)
    task_history.log = log_filename
    task_history.save()
    return logger

class TaskRunner:
    @classmethod
    def name(cls):
        return cls.__name__

    @classmethod
    def run(cls, task: Task, run_type: str):
        pass

    @classmethod
    def help_text(cls):
        pass

    @classmethod
    def needed_arguments(cls):
        pass

    @classmethod
    def needed_connections(cls):
        pass

class TestRunner(TaskRunner):
    @classmethod
    def run(cls, task: Task, run_type: str):
        task_history = TaskHistory.objects.create(
            task=task,
            run_type=run_type,
            status="RUNNING"
        )
        logger = set_logger_config(task, task_history)
        try:
            logger.info(f"Task {task.name} started at {task_history.started_at}")
            endTime = datetime.now() + timedelta(minutes=1)
            connections = task.connections.all()
            logger.info(f"Task {task.name} is running for 1 minute")
            while True:
                if datetime.now() >= endTime:
                    break
            logger.info(f"Task {task.name} ran for 1 minute")
            if not connections.exists():
                raise Exception("No connections found")
            output = pd.DataFrame([[random.randint(0,100), random.randint(0,100)]]*5 ,columns=["Column1","Column2"])
            output_filename = get_file_location(task_history,"outputs","csv")
            output.index.names = ["Index"]
            output.to_csv(output_filename, sep=CSV_SEPARATOR)
            logger.info(f"Output is saved successfully")
            task_history.status = "SUCCESS"
            task_history.output = output_filename
        except Exception as e:
            task_history.status = "FAILED"
            logger.error(e)
        finally:
            task_history.ended_at = datetime.now(timezone.utc)
            task_history.save()
            logger.info(f"Task {task.name} ended at {task_history.ended_at}")

    @classmethod
    def help_text(cls):
        return "This is a test task. It runs for 1 minute in a while loop. It also checks if one connection is present. It will fail if no connection is passed to this task."
    
    @classmethod
    def needed_arguments(cls):
        return []
    
    @classmethod
    def needed_connections(cls):
        return 1
    
    @classmethod
    def name(cls):
        return "Test Runner"

class ReconnaissanceRunner(TaskRunner):
    @classmethod
    def name(cls):
        return "Reconnaissance Runner"
    
    @classmethod
    def run(cls, task: Task, run_type: str):
        task_history = TaskHistory.objects.create(
            task=task,
            run_type=run_type,
            status="RUNNING"
        )
        logger = set_logger_config(task, task_history)
        try:
            logger.info(f"Task {task.name} started at {task_history.started_at}")
            connections = task.connections.all()
            if not connections.exists():
                raise Exception("No connections found")
            connection:Connection = connections.first()
            logger.info(f"Connection {connection.name} is being used as default connection")
            connection = connection.child_model_instance()
            connection.connect_to_database()
            logger.info(f"Connection {connection.name} is connected")
            schemas = [ x[1] for x in connection.execute_query("SHOW SCHEMAS") ]
            logger.info(f"Connection {connection.name} has {len(schemas)} schemas")
            schemas_string = ",".join([f"'{x}'" for x in schemas])
            args = task.arguments.all()
            if args.count() != 2:
                raise Exception("Invalid number of arguments")
            logger.info(f"Task {task.name} has {len(args)} arguments")
            SOURCE_DATABASE = args.get(name="SOURCE_DATABASE").value
            TARGET_DATABASE = args.get(name="TARGET_DATABASE").value
            query = f" SELECT 'select '||''''||TABLE_SCHEMA||'.'||TABLE_NAME ||''' as name , (select count(*) from {TARGET_DATABASE}.'||TABLE_SCHEMA||'.'||TABLE_NAME|| ' ) = (SELECT count(*) FROM {SOURCE_DATABASE}.'||TABLE_SCHEMA||'.'||TABLE_NAME||') AS MATCH_TRUE_FALSE, (select count(*) from {TARGET_DATABASE}.'||TABLE_SCHEMA||'.'||TABLE_NAME|| ') as {TARGET_DATABASE} , (SELECT count(*) FROM {SOURCE_DATABASE}.'||TABLE_SCHEMA||'.'||TABLE_NAME||') AS {SOURCE_DATABASE} FROM DUAL;' FROM {SOURCE_DATABASE}.INFORMATION_SCHEMA.TABLES WHERE table_type = 'BASE TABLE' and table_schema in ({schemas_string})"
            logger.info(f"Executing generated query is {query}")
            commands_table = connection.execute_query(query)
            logger.info(f"Query executed successfully")
            output = []
            for command in commands_table:
                try:
                    logger.info(f"Executing command {command[0]}")
                    output.append(connection.execute_query(command[0])[0])
                    logger.info(f"Command executed successfully")
                except Exception as e:
                    logger.error(f"Error in executing command {command[0]}")
                    logger.error(e)
                    x = re.search(r"'(.*?)'", command[0]).group(1)
                    schema = x.split(".")[0]
                    table = x.split(".")[1]
                    logger.info(f"Getting count of {schema}.{table} from {SOURCE_DATABASE}")
                    source_count = connection.execute_query(f"SELECT count(*) FROM {SOURCE_DATABASE}.{schema}.{table}")[0][0]
                    output.append((schema+"."+table,False,0,source_count))
                logger.info(f"Table {table} is compared successfully")
            output = pd.DataFrame(output,columns=["Name","Matches",f"{TARGET_DATABASE}",f"{SOURCE_DATABASE}"])
            output.index.names = ["Index"]
            output = output[["Name","Matches",f"{SOURCE_DATABASE}",f"{TARGET_DATABASE}"]]
            logger.info(f"Output is generated successfully")
            output_filename = get_file_location(task_history,"outputs","csv")
            output.index.names = ["Index"]
            output.to_csv(output_filename, sep=CSV_SEPARATOR)
            logger.info(f"Output is saved successfully")
            task_history.status = "SUCCESS"
            task_history.output = output_filename
        except Exception as e:
            task_history.status = "FAILED"
            logger.error(e)
        finally:
            task_history.ended_at = datetime.now(timezone.utc)
            task_history.save()
            logger.info(f"Task {task.name} ended at {task_history.ended_at}")
            connection.close_connection()
            logger.info(f"Connection {connection.name} is closed")

    @classmethod
    def help_text(cls):
        return "This task compares two databases and their tables. Count of rows in each table is compared."
    
    @classmethod
    def needed_arguments(cls):
        return ["SOURCE_DATABASE","TARGET_DATABASE"]
    
    @classmethod
    def needed_connections(cls):
        return 1

class SummaryRunner(TaskRunner):
    @classmethod
    def name(cls):
        return "Summary Runner"
    
    @classmethod
    def run(cls, task: Task, run_type: str):
        task_history = TaskHistory.objects.create(
            task=task,
            run_type=run_type,
            status="RUNNING"
        )
        logger = set_logger_config(task, task_history)
        try:
            logger.info(f"Task {task.name} started at {task_history.started_at}")
            connections = task.connections.all()
            if not connections.exists():
                raise Exception("No connections found")
            connection:Connection = connections.first()
            logger.info(f"Connection {connection.name} is being used as default connection")
            connection = connection.child_model_instance()
            connection.connect_to_database()
            logger.info(f"Connection {connection.name} is connected")
            args = task.arguments.all()
            SOURCE_DATABASE = args.get(name="SOURCE_DATABASE").value
            TARGET_DATABASE = args.get(name="TARGET_DATABASE").value
            SCHEMA = args.get(name="SCHEMA").value
            logger.info(f"Task {task.name} has {len(args)} arguments")
            logger.info(f"Source database is {SOURCE_DATABASE}")
            logger.info(f"Target database is {TARGET_DATABASE}")
            logger.info(f"Schema is {SCHEMA}")
            tables = [ x[1] for x in connection.execute_query(f"SHOW TABLES FROM {SCHEMA}") ]
            logger.info(f"Connection {connection.name} has {len(tables)} tables in {SCHEMA}")
            

        except Exception as e:
            task_history.status = "FAILED"
            logger.error(e)
        finally:
            task_history.ended_at = datetime.now(timezone.utc)
            task_history.save()
            logger.info(f"Task {task.name} ended at {task_history.ended_at}")
            connection.close_connection()
            logger.info(f"Connection {connection.name} is closed")

    @classmethod
    def help_text(cls):
        return "This task generates a summary of the tables in a schema. The summary includes the number of rows that are not in source, not in target, and mismatched rows count."

    @classmethod
    def needed_arguments(cls):
        return ["SOURCE_DATABASE","TARGET_DATABASE","SCHEMA"]
    
    @classmethod
    def needed_connections(cls):
        return 1
    
TASK_TYPES:dict[str,object] = {
    Task.RECONNAISSANCE: ReconnaissanceRunner,
    Task.TEST: TestRunner,
}
