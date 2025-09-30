package main

import (
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	v1 := r.Group("/api/v1")
	{
		v1.GET("/hello", func(c *gin.Context) {
			c.JSON(200, gin.H{"message": "Ok"})
		})
	}
	r.Run(":8080")
}
