from typing import Any
from django.db import models
from django.contrib.auth.models import AbstractBaseUser,PermissionsMixin
from django.core.validators import validate_domain_name
from django.utils.translation import gettext_lazy as _
from background_task.models import Task as BackgroundTask

from redshift_connector import connect as redshift_connect

from snowflake.connector import connect as snowflake_connect, SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor

from .managers import UserManager

class Company(models.Model):
    name = models.CharField(_("Company Name"),max_length=255)
    domain_name = models.CharField(_("Domain Name"),unique=True ,max_length=255,validators=[validate_domain_name])
    manager = models.ForeignKey("User",on_delete=models.CASCADE,related_name="companies_managed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("Email Address"),unique=True,max_length=127)
    name = models.CharField(_("Name"),max_length=255)
    company = models.ForeignKey(Company,on_delete=models.SET_NULL,related_name="users",null=True,blank=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return self.name

    
class Connection(models.Model):
    CONNECTION_TYPES = [
        ("snowflakeconnection","Snowflake Connection"),
        ("redshiftconnection","Redshift Connection"),
    ]

    name = models.CharField(_("Connection Name"),max_length=255)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name="connections")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_connectable(self) -> bool:
        return self.type() != "Connection"

    def type(self) -> str:
        for connection_type in self.CONNECTION_TYPES:
            if hasattr(self, connection_type[0]):
                return connection_type[1]
        return "Connection"
    
    def type_class(self) -> str:
        for connection_type in self.CONNECTION_TYPES:
            if hasattr(self, connection_type[0]):
                return connection_type[0]
        return "Connection"
    
    def child_model_instance(self) -> models.Model:
        if self.is_connectable():
            return getattr(self, self.type_class())
        return self

    def get_fields(self) -> list[str]:
        return []

    def connect_to_database(self):
        raise NotImplementedError("The connect method must be implemented in the child class.")
    
    def execute_query(self, query:str) -> tuple[list[str],list[tuple]]:
        raise NotImplementedError("The execute method must be implemented in the child class.")
    
    def close_connection(self):
        raise NotImplementedError("The close_connection method must be implemented in the child class.")

    def __str__(self) -> str:
        return self.name
    
class RedshiftConnection(Connection):
    host = models.CharField(_("Host"),max_length=255)
    port = models.IntegerField(_("Port"))
    username = models.CharField(_("Username"),max_length=255)
    password = models.CharField(_("Password"),max_length=255)
    database = models.CharField(_("Database"),max_length=255)

    def type(self) -> str:
        return "Redshift Connection"
    
    def get_fields(self) -> list[str]:
        return [("Host",self.host),("Port",self.port),("Username",self.username), ("Password",self.password),("Database",self.database),]
    
    def connect_to_database(self):
        self.connection = redshift_connect(
            user=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database
        )
        self.cursor = self.connection.cursor()
    
    def execute_query(self, query:str) -> list[tuple] | list[dict]:
        self.cursor.execute(query)
        return self.cursor.fetchall()
    
    def close_connection(self):
        self.cursor.close()
        self.connection.close()
        self.cursor = None
        self.connection = None

    class Meta:
        default_permissions = ()

class SnowflakeConnection(Connection):
    account = models.CharField(_("Account"),max_length=255)
    username = models.CharField(_("Username"),max_length=255)
    password = models.CharField(_("Password"),max_length=255)
    warehouse = models.CharField(_("Warehouse"),max_length=255)
    database = models.CharField(_("Database"),max_length=255,null=True,blank=True)
    schema = models.CharField(_("Schema"),max_length=255,null=True,blank=True)

    def type(self) -> str:
        return "Snowflake Connection"
    
    def get_fields(self) -> list[str]:
        return [("Account",self.account),("Username",self.username), ("Password",self.password),("Warehouse",self.warehouse),("Database",self.database),("Schema",self.schema)]
    
    def connect_to_database(self):
        self.connection: SnowflakeConnection = snowflake_connect(
            user=self.username,
            password=self.password,
            account=self.account,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema
        )
        self.cursor: SnowflakeCursor = self.connection.cursor()
    
    def execute_query(self, query:str) -> list[tuple] | list[dict]:
        self.cursor.execute(query)
        return self.cursor.fetchall()
    
    def close_connection(self):
        self.cursor.close()
        self.connection.close()
        self.cursor = None
        self.connection = None

    class Meta:
        default_permissions = ()
    
class Task(models.Model):
    RECONNAISSANCE = "RECONNAISSANCE"
    TEST = "TEST"

    TYPE_CHOICES = [
        (RECONNAISSANCE,"Reconnaissance (1 Connection)"),
        (TEST,"Test"),
    ]

    NEVER = BackgroundTask.NEVER
    HOURLY = BackgroundTask.HOURLY
    DAILY = BackgroundTask.DAILY
    WEEKLY = BackgroundTask.WEEKLY
    MONTHLY = BackgroundTask.EVERY_4_WEEKS

    INTERVAL_CHOICES = [
        (NEVER,'Never'),
        (HOURLY,'Hourly'),
        (DAILY,'Daily'),
        (WEEKLY,'Weekly'),
        (MONTHLY,'Monthly'),
    ]

    name = models.CharField(_("Task Name"),max_length=255)
    type = models.CharField(_("Task type"),max_length=127,choices=TYPE_CHOICES,default=RECONNAISSANCE)

    recurrence_interval = models.IntegerField(_("Interval"),choices=INTERVAL_CHOICES,default=NEVER)
    run_at = models.DateTimeField(_("Start At"))

    created_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name="tasks")
    connections = models.ManyToManyField(Connection,related_name="tasks",blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self) -> str:
        return self.name
    
    def get_arguments_needed(self) -> list[str]:
        if self.type == self.RECONNAISSANCE:
            return ["SOURCE_DATABASE","TARGET_DATABASE"]
        return []
    
class TaskHistory(models.Model):
    task = models.ForeignKey(Task,on_delete=models.CASCADE,related_name="history")
    started_at = models.DateTimeField(_("Started At"),auto_now_add=True)
    ended_at = models.DateTimeField(_("Ended At"),null=True,blank=True)
    run_type = models.CharField(_("Task run type"),max_length=127)
    status = models.CharField(_("Status"),max_length=255)
    log = models.FileField(_("Log"),null=True,blank=True)
    output = models.FileField(_("Output"),null=True,blank=True)

    def __str__(self) -> str:
        return f"{self.task.name} - {self.started_at}"
    
    def delete(self, using: Any = ..., keep_parents: bool = ...) -> tuple[int, dict[str, int]]:
        self.log.delete()
        self.output.delete()
        return super().delete(using, keep_parents)

class TaskArgument(models.Model):
    task = models.ForeignKey(Task,on_delete=models.CASCADE,related_name="arguments")
    name = models.CharField(_("Argument Name"),max_length=255)
    value = models.CharField(_("Argument Value"),max_length=255)

    def __str__(self) -> str:
        return f"{self.task.name} - {self.name}"

class SingletonModel(models.Model):
    """Singleton Django Model"""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Save object to the database. Removes all other entries if there
        are any.
        """
        self.__class__.objects.exclude(id=self.id).delete()
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.__class__.objects.create()
        super(SingletonModel, self).delete(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Load object from the database. Failing that, create a new empty
        (default) instance of the object and return it.
        """
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            obj = cls()
            obj.save()
            return obj
        
class Setting(SingletonModel):
    user_registration = models.BooleanField(_("User Registration"),default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
