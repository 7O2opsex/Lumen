# Lumen - Advanced Local OSINT Desktop Application

**100% Local Data Processing with GUI**

## 🎯 Objectif

Lumen est un outil OSINT complètement local. Toutes les données restent sur la machine de l'utilisateur. L'application se compile en un seul fichier `.exe` autonome sans dépendances externes.

## 📋 Caractéristiques

### 1. Exif & Meta
- 🖼️ Drag & drop d'images (JPG, PNG, WebP, TIFF) et PDF
- 📊 Extraction complète EXIF / XMP / IPTC / GPS
- 🔍 Métadonnées présentées en sections lisibles et nommées
- 🧹 Nettoyage des métadonnées (totale ou sélective)
- 👁️ Prévisualisation avant/après
- 💾 Export JSON et TXT

### Apparence
- 🎨 Thèmes Violet, Clair rouge et blanc, Marron et Obsidienne dorée
- ⚙️ Choix du thème et de la couleur principale depuis les réglages
- 💾 Préférences d'apparence mémorisées localement dans `data/lumen_settings.json`
- ✨ Obsidienne dorée est un thème caché cosmétique : `Ctrl + Maj + L`, puis saisir `ilovelumen`
- 🔒 Le thème caché n'active aucun abonnement ni fonctionnalité payante

### 2. Identity
- 👤 **UserMap** : Recherche de pseudo sur une liste de sites configurables
- 📝 **NameCheck** : Génération de variations de noms
- 🔗 **CrossRef** : Corrélation basique entre deux identifiants

### 3. Links
- 🔗 Résolution complète des redirections de liens raccourcis
- 📍 Affichage de chaque étape + URL finale
- ⚠️ Détection basique de domaines suspects

### 4. Dashboard
- 📜 Historique local (SQLite)
- 📤 Export des résultats
- 🔒 Aucune donnée envoyée sans action explicite de l'utilisateur

## 🛠️ Stack Technique

- **Python 3.11+**
- **CustomTkinter** - Interface moderne et responsive
- **Pillow + piexif + PyPDF2** - Métadonnées
- **requests** - Requêtes volontaires (réseau local only)
- **PyInstaller** - Compilation en .exe
- **SQLite3** - Base de données locale

## 📁 Structure du Projet

```
Lumen/
├── main.py                          # Point d'entrée principal
├── requirements.txt                 # Dépendances Python
├── launch.bat                       # Installation des dépendances et lancement Windows
├── lumen/
│   ├── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py          # Fenêtre principale
│   │   ├── tabs/
│   │   │   ├── __init__.py
│   │   │   ├── exif_tab.py         # Tab Exif & Meta
│   │   │   ├── identity_tab.py     # Tab Identity
│   │   │   ├── links_tab.py        # Tab Links
│   │   │   └── dashboard_tab.py    # Tab Dashboard
│   │   └── styles.py               # Thème et couleurs
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exif_processor.py       # Extraction EXIF
│   │   ├── identity_processor.py   # Traitement identité
│   │   ├── link_resolver.py        # Résolution de liens
│   │   └── validators.py           # Validation de domaines
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── json_exporter.py        # Export JSON
│   │   ├── txt_exporter.py         # Export TXT
│   │   └── csv_exporter.py         # Export CSV
│   ├── network/
│   │   ├── __init__.py
│   │   └── request_handler.py      # Gestion des requêtes réseau
│   ├── database/
│   │   ├── __init__.py
│   │   └── local_storage.py        # SQLite local
│   └── config.py                   # Configuration globale
├── build_exe.bat                    # Script de compilation Windows
├── build_exe.sh                     # Script de compilation Linux/Mac
└── .gitignore
```

## 🚀 Installation & Démarrage

### Prérequis
- Python 3.11 ou supérieur
- pip

### Installation

#### Windows (automatique)

Double-cliquez sur `launch.bat` à la racine du projet. Le script crée un environnement virtuel `.venv` s'il n'existe pas, installe les dépendances, puis lance l'application. Python 3.11 ou supérieur doit être installé.

#### Installation manuelle

```bash
# Cloner le dépôt
git clone https://github.com/7O2opsex/Lumen.git
cd Lumen

# Créer un environnement virtuel
python -m venv .venv

# Activer l'environnement virtuel
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### Lancer l'application

```bash
python main.py
```

## 📦 Compilation en .exe

### Windows (Automatisé)

```bash
# Utiliser le script batch
build_exe.bat
```

### Commande manuelle

```bash
pyinstaller --noconfirm --onefile --windowed --name Lumen --icon=icon.ico main.py
```

Le fichier `.exe` sera généré dans `dist/Lumen.exe`

## 🔒 Architecture : Local vs Réseau

### ✅ 100% Local
- Extraction et traitement EXIF / XMP / IPTC / GPS
- Nettoyage des métadonnées
- Génération de variations de noms
- Stockage de l'historique (SQLite)
- Toutes les opérations d'analyse

### 🌐 Réseau (sur demande explicite)
- Recherche UserMap (optionnel, sur les sites configurés)
- Résolution de liens raccourcis (suivi des redirections)
- **Toujours nécessite une action explicite de l'utilisateur**
- **Jamais de collecte de données en arrière-plan**

## 📋 Checklist de Conformité

- ✅ Compilable en .exe avec PyInstaller `--onefile --windowed`
- ✅ Interface CustomTkinter sombre et moderne
- ✅ Drag & drop natif
- ✅ Aucune donnée envoyée sans action explicite
- ✅ Code typé et commenté
- ✅ Gestion d'erreurs robuste
- ✅ Séparation modulaire stricte
- ✅ SQLite pour historique local
- ✅ Export JSON, TXT, CSV

## 📄 Licence

MIT License - Voir LICENSE pour plus de détails

## 👤 Auteur

7O2opsex

---

**Note de Sécurité** : Lumen ne collecte, n'envoie, ni ne stocke aucune donnée sur des serveurs distants sans votre consentement explicite.