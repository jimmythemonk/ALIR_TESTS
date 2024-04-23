@echo off
rem Compile the C source file into an object file
gcc -c -o rice.o rice.c

gcc -shared -o rice.so -fPIC rice.c

rem Create the DLL from the object file
gcc -shared -o rice.dll rice.o

