cppinterp
=========

Exactly what it sounds like. cppinterp's goal is to allow very quick and easy testing of small bits of C++ functionality through small snippets of code in a gcc-based REPL-like CLI environment. It is not a REPL nor real interpreter, and depends upon just enough code modification and a wrapper around GCC for its guise.

##Usage Examples
```>>> hello world
1:1: error: ‘hello’ was not declared in this scope
1:7: error: expected ‘;’ before ‘world’
>>> cout << "hello world" << endl;
hello world
>>> int z = 5;
>>> z += 100 +\
...      0x0a;
>>> cout << z << endl;
115
>>> int square(int a) \
... {\
...   return a*a;\
... }
>>> cout << square(5) << endl;
25
>>>```

####Includes
If libraries are requested requiring modifying LFLAGS/CFLAGS, cppinterp will invoke [supermake](http://personalcomputer.github.io/supermake/) behind the scenes, creating a powerful experimentation environment.

```>>> #include <mysql/mysql.h>
>>> MYSQL* mysql = mysql_init(NULL);
1:27: error: ‘NULL’ was not declared in this scope
>>> #include <cstdlib>
>>> MYSQL* mysql = mysql_init(NULL);
>>> cout << mysql_real_connect(mysql, "localhost", "test", "test", "test",0,0,0) << endl;
0
>>> cout << mysql_error(mysql) << endl;
Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)
>>>```
