# Architecture SUPCORRECT

Le point d'entrée est HAProxy. Il force HTTPS et distribue les requêtes vers deux nœuds identiques, `web-1` et `web-2`. Chaque nœud exécute Apache devant Gunicorn et la même version de l'application.

MariaDB primaire reçoit les écritures de l'application et réplique les binlogs en GTID vers MariaDB replica. La replica est contrôlée par `SHOW REPLICA STATUS`. Un worker dédié récupère les jobs dans la table `jobs`, puis écrit le résultat sur le primaire.

Le worker est volontairement séparé des processus web. Un dépôt HTTP ne lance jamais le programme de l'étudiant : il ne fait qu'écrire une soumission et un job dans la même transaction.

La perte d'un nœud web est absorbée par HAProxy. La réplication protège les données ; la promotion de la replica reste une opération documentée et contrôlée, afin d'éviter un faux multi-maître à deux nœuds.
