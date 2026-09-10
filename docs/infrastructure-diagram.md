# Diagramme d'infrastructure SUPCORRECT

```text
                         Poste étudiant
                               |
                         HTTPS :443
                               v
                    +--------------------+
                    |      HAProxy       |
                    | TLS + health check |
                    +--------------------+
                         |            |
                         v            v
              +---------------+  +---------------+
              |     web-1     |  |     web-2     |
              | Apache        |  | Apache        |
              | Gunicorn      |  | Gunicorn      |
              +---------------+  +---------------+
                         |            |
                         +-----+------+ 
                               |
                               v
                    +--------------------+
                    | MariaDB primaire   |
                    | écritures + jobs   |
                    +--------------------+
                               |
                         GTID replication
                               v
                    +--------------------+
                    | MariaDB replica    |
                    | lecture/reprise    |
                    +--------------------+

              +-----------------------------------+
              | Worker SUPCORRECT (compte grader) |
              | bubblewrap, gcc, python, systemd  |
              +-----------------------------------+
                               |
                    lecture/écriture des jobs
                               |
                               v
                    MariaDB primaire
```

Les programmes soumis ne sont jamais exécutés par Apache. Le worker récupère la soumission dans la file SQL, exécute le programme et le corrigé de référence dans deux sandboxes séparées, puis écrit la note et supprime le source.
