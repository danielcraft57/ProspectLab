# Configurer PostgreSQL pour l'accès distant

Par défaut, PostgreSQL n'écoute que sur localhost (127.0.0.1). Pour permettre les connexions depuis Windows ou d'autres machines du réseau, il faut modifier la configuration.

## Étape 1 : Modifier postgresql.conf

Sur le serveur, édite le fichier de configuration :

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

Trouve la ligne `listen_addresses` et modifie-la :

```conf
# Avant (par défaut)
# listen_addresses = 'localhost'

# Après (pour accepter les connexions depuis le réseau local)
listen_addresses = '*'
# Ou pour être plus sécurisé, seulement le réseau local :
# listen_addresses = '127.0.0.1,192.168.1.0/24'
```

## Étape 2 : Configurer pg_hba.conf

Édite le fichier d'authentification :

```bash
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

Ajoute une ligne pour autoriser les connexions depuis le réseau local (192.168.1.0/24) :

```conf
# Connexions locales (déjà présent)
local   all             all                                     peer

# Connexions IPv4 depuis le réseau local
host    all             all             192.168.1.0/24          md5

# Connexions IPv6 depuis le réseau local (optionnel)
host    all             all             ::1/128                  md5
```

**Important :** Remplace `192.168.1.0/24` par ton réseau local si différent.

## Étape 3 : Redémarrer PostgreSQL

```bash
sudo systemctl restart postgresql
```

## Étape 4 : Vérifier que PostgreSQL écoute sur toutes les interfaces

```bash
sudo ss -tlnp | grep 5432
```

Tu devrais voir :
```
tcp   LISTEN 0  244  0.0.0.0:5432  0.0.0.0:*  users:(("postgres",pid=...))
```

Au lieu de seulement `127.0.0.1:5432`.

## Étape 5 : Tester la connexion depuis Windows

Depuis Windows, avec DBeaver ou pgAdmin, utilise :

```
Host: <HOTE_SERVEUR> (ex. serveur.lan ou IP)
Port: 5432
Database: prospectlab
Username: prospectlab
Password: [ton mot de passe]
```

## Sécurité

⚠️ **Important :** Autoriser l'accès depuis le réseau local est acceptable pour un réseau privé (192.168.x.x), mais :

1. **Ne jamais** exposer PostgreSQL directement sur Internet
2. Utilise un firewall pour bloquer le port 5432 depuis l'extérieur
3. Utilise des mots de passe forts
4. Considère l'utilisation d'un tunnel SSH pour plus de sécurité

## Alternative : Tunnel SSH (Plus sécurisé)

Si tu veux éviter d'exposer PostgreSQL sur le réseau, tu peux utiliser un tunnel SSH :

```bash
# Depuis Windows (PowerShell)
ssh -L 5432:localhost:5432 <UTILISATEUR>@<SERVEUR>
```

Puis dans DBeaver/pgAdmin, utilise :
```
Host: localhost
Port: 5432
```

Le trafic passera par le tunnel SSH sécurisé.
