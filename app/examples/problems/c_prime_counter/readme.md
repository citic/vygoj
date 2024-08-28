# Contador de primos en C

Se necesita mejorar el rendimiento de un programa que recibe números enteros positivos en la entrada estándar e indica cuántos y cuáles de ellos son primos. Se quiere paralelizar el programa para que sea multihilo usando C11 estándar. El programa recibe la cantidad de hilos como primer valor de la entrada estándar. Como segundo valor se indica la cantidad de números que se quieren probar. En las líneas subsecuentes se proveen dichos números.

*Ejemplo de entrada*:

```
3 5
9
7
6
2
1
```

*Ejemplo de salida*:

```
2 primes:
7
2
```

El programa debe indicar en la salida estándar la cantidad de primos encontrada y en las líneas subsecuentes listar esos primos en el mismo orden en que fueron ingresados en la entrada estándar. Dado que no se sabe de antemano qué números serán provistos al programa, éste debe mapearlos de forma dinámica entre los hilos, con el fin de balancear mejor la carga de trabajo y proveer un mejor tiempo de respuesta.
