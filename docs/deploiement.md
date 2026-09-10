# Déploiement

Le projet se déploie sur six rôles : `load-balancer`, `web-1`, `web-2`, `db-primary`, `db-replica` et un `worker` dédié. Le worker ne doit pas partager le compte de service web.

## Ordre d'installation

La cible retenue est Ubuntu Server 24.04 LTS avec MariaDB 10.11 ou version compatible GTID. Prévoir une résolution DNS ou des entrées `/etc/hosts` cohérentes pour `db-primary.internal`, les deux nœuds web et le répartiteur. Autoriser uniquement les flux nécessaires : HAProxy vers les web nodes en TCP 8080, web nodes et worker vers MariaDB en TCP 3306, et primaire vers replica en TCP 3306.

1. Installer MariaDB sur les deux nœuds DB avec `scripts/install-database.sh primary` ou `scripts/install-database.sh replica`. Le script copie la configuration dans `/etc/mysql/mariadb.conf.d/60-supcorrect.cnf`, redémarre MariaDB et vérifie sa disponibilité.
2. Sur le primaire, lancer `scripts/provision-primary.sh` avec les cinq variables de mot de passe exportées dans le shell. Le compte de sauvegarde créé est `supcorrect_backup`.
3. Exporter le primaire avec `scripts/backup-primary.sh` en définissant explicitement `PRIMARY_HOST`, `MYSQL_BACKUP_USER`, `MYSQL_BACKUP_PASSWORD` et `BACKUP_FILE`. Transférer ce fichier par un canal sécurisé vers la replica.
4. Sur la replica, restaurer ce fichier avec `scripts/restore-replica.sh`, lancer `scripts/provision-accounts.sh` avec les mêmes mots de passe et `DB_CLIENT_CIDR`, puis lancer `scripts/configure-replica.sh`. Vérifier que `Slave_IO_Running` et `Slave_SQL_Running` sont à `Yes`.
5. Lancer `scripts/install-web.sh` sur `web-1`, puis `web-2`. Remplacer les valeurs de `/etc/supcorrect/app.env` avant de redémarrer `supcorrect-web`.
6. Lancer `scripts/install-worker.sh` sur le worker, adapter son `/etc/supcorrect/app.env`, puis démarrer `supcorrect-worker`.
7. Lancer `scripts/install-load-balancer.sh`, installer le certificat TLS et activer HAProxy.

Pour une base installée avec une ancienne V1, faire une sauvegarde puis exécuter une seule fois `mysql -u root -p < infra/database/migrate_v1_to_v2_mariadb.sql` avant de déployer le worker V2. Une installation vierge utilise directement `schema_mariadb.sql` et ne doit pas exécuter cette migration.

## Avant mise en service

Les adresses `10.0.0.x` de `infra/haproxy/haproxy.cfg` et `DB_CLIENT_CIDR` sont des exemples et doivent être remplacées par les valeurs du laboratoire. Les mots de passe doivent être générés avec un alphabet URL-compatible, car ils sont inclus dans `DATABASE_URL`. Les fichiers `/etc/supcorrect/app.env` restent hors Git et ont les droits `0640`. `FLASK_SECRET_KEY` doit être forte et strictement identique sur `web-1` et `web-2`, afin de préserver les sessions réparties par HAProxy.

## Contrôles

`curl -I http://adresse-du-lb` doit retourner une redirection HTTPS. `curl -fsS https://adresse-du-lb/health` doit retourner `{"status":"ok"}`. Une soumission correcte doit passer de l'attente à une note, puis la colonne `source_code` doit être `NULL` dans MariaDB. Arrêter Apache sur un des deux nœuds web ne doit pas rendre le site indisponible.

Sur chaque rôle installé, utiliser `scripts/check-infra.sh web`, `scripts/check-infra.sh worker` ou `scripts/check-infra.sh load-balancer` pour valider la configuration réellement chargée par le service concerné.
