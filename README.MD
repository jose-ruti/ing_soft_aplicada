## Requisitos

Sigue estos pasos para configurar y ejecutar el proyecto:

1. **Instalar Golang**  
    Descarga e instala Go desde [golang.org](https://golang.org/dl/).

2. **Inicializar el módulo del proyecto**  
    ```bash
    go mod init nombre-del-proyecto
    ```

3. **Instalar dependencias**  
    ```bash
    go get github.com/gin-gonic/gin
    ```

4. **Ejecutar la aplicación**  
    ```bash
    go run main.go
    ```

5. **Probar la API con Postman**  
    Accede a: [http://localhost:8080/api/v1/hello](http://localhost:8080/api/v1/hello)

6. **Construir la imagen Docker**  
    ```bash
    docker build -t azure-app:v1.0 .
    ```
