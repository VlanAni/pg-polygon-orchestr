## Как ставить ограничения на CPU

https://man7.org/linux/man-pages/man7/cgroups.7.html

https://docs.docker.com/engine/containers/resource_constraints/#cpu

Для ограничения ресурсов CPU, которые может использовать Docker Container, можно использовать флаг `--cpus=<number>`

В `dockerSDK` есть кроссплатформенный аналог `nano_cpus` (используется в коде на данный момент, поскольку другой аргумент работает только для Windows)

## Ограничения на memory

https://docs.docker.com/engine/containers/resource_constraints/#memory

`Docker` позволяет устанавливать *мягкие* и *жёсткие* ограничения на память для контейнера

В коде используется жёсткие ограничения, поскольку они позоляют обеспечить, что у сервера определённое количество памяти

Наиболее подходящий флаг `Docker`'а - `--memory`