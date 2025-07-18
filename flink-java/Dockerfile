FROM eclipse-temurin:23-jdk

WORKDIR /app

COPY build/libs/flink-java-1.0-SNAPSHOT.jar app.jar

EXPOSE 9249

ENTRYPOINT ["java", "-jar", "app.jar"]