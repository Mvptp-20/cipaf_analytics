README.md
---

# 📊 CIPAF Analytics (Versión en Español)

Repositorio para los flujos de trabajo analíticos de CIPAF, incluyendo automatización, documentación, activos de reportes y scripts de investigación.

## 📁 Estructura del Proyecto

- `docs/` → Documentación y notas de procesos
- `reports/` → Carpetas de proyectos y activos de reportes
- `scripts/python/` → Scripts de automatización e investigación
- `themes/` → Temas de Power BI
- `outputs/` → Resultados generados por scripts (excluidos del repositorio)

## ⚙️ Scripts Principales

- `scout_cipaf.py` → Recolecta y evalúa fuentes en línea según relevancia y confianza
- `download_cipaf.py` → Descarga información desde fuentes identificadas
- `organize_inventory.py` → Organiza archivos y datos
- `triage_cipaf.py` → Clasifica y prioriza información recolectada

## 🧩 Instalación

```bash
pip install -r requirements.txt

▶️ Uso

Desde la carpeta raíz del proyecto:

py scripts\python\scout_cipaf.py
📤 Resultados

Los resultados se guardan en:

outputs/<nombre_del_folder>/

Archivos generados:

*_ALL.txt → Todas las fuentes recolectadas
*_HIGH.txt → Fuentes con alta confianza
📝 Notas
Diseñado para flujos de investigación exploratoria
El sistema de puntuación de confianza puede ajustarse según necesidades


# CIPAF Analytics

Repository for CIPAF analytics workflows, research scripts, Power BI themes, documentation, and reporting assets.

## Structure

- `docs/` → documentation and process notes
- `reports/` → project folders and report assets
- `scripts/python/` → automation and research scripts
- `themes/` → Power BI theme files
- `outputs/` → generated script outputs (ignored in Git)

## Main Scripts

- `scout_cipaf.py` → collects and scores online sources
- `download_cipaf.py`
- `organize_inventory.py`
- `triage_cipaf.py`

## Install

```bash
pip install -r requirements.txt