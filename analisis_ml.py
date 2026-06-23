# ═══════════════════════════════════════════════════════════════
#  WORLD SIMULATION  –  Análisis ML / Redes Neuronales
#
#  Ejecutar DESPUÉS de una o varias sesiones del simulador:
#    python analisis_ml.py
#
#  Requiere:
#    pip install pandas numpy scikit-learn matplotlib seaborn networkx
# ═══════════════════════════════════════════════════════════════

import os, json, warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")    # sin ventana (para ejecutar en cualquier entorno)
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns

from sklearn.preprocessing   import LabelEncoder, StandardScaler
from sklearn.decomposition   import PCA
from sklearn.cluster         import KMeans, DBSCAN
from sklearn.ensemble        import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network  import MLPClassifier, MLPRegressor
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics         import (classification_report, confusion_matrix,
                                     silhouette_score)
from sklearn.manifold        import TSNE
import networkx as nx

DATA_DIR   = "data"
OUTPUT_DIR = "analisis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="darkgrid", palette="muted")
TRAIT_COLORS = {
    "amigable":"#4CAF50","timido":"#2196F3","curioso":"#FF9800",
    "agresivo":"#F44336","perezoso":"#9C27B0","energetico":"#00BCD4",
    "melancolico":"#607D8B","optimista":"#FFEB3B",
}

def load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.isfile(p):
        print(f"  [FALTA] {name} – ejecuta el simulador primero.")
        return None
    return pd.read_csv(p)

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ══════════════════════════════════════════════════════════════
#  1. CARGA DE DATOS
# ══════════════════════════════════════════════════════════════
section("1. CARGA DE DATOS")

agents  = load("agents.csv")
needs   = load("needs_timeseries.csv")
states  = load("state_events.csv")
convs   = load("conversations.csv")
edges   = load("social_edges.csv")
utts    = load("utterances.csv")

if agents is None:
    print("No hay datos. Ejecuta WORLD_simulation primero.")
    exit(0)

print(f"  Agentes:       {len(agents)} registros")
print(f"  Necesidades:   {len(needs) if needs is not None else 0} snapshots")
print(f"  Eventos FSM:   {len(states) if states is not None else 0} transiciones")
print(f"  Conversaciones:{len(convs) if convs is not None else 0}")
print(f"  Bordes social: {len(edges) if edges is not None else 0}")
print(f"  Turnos diálogo:{len(utts) if utts is not None else 0}")


# ══════════════════════════════════════════════════════════════
#  2. ANÁLISIS DE PERSONALIDADES
# ══════════════════════════════════════════════════════════════
section("2. DISTRIBUCIÓN DE PERSONALIDADES")

trait_counts = agents["trait"].value_counts()
print(trait_counts.to_string())

fig, ax = plt.subplots(figsize=(10, 5))
colors  = [TRAIT_COLORS.get(t, "#888") for t in trait_counts.index]
trait_counts.plot(kind="bar", ax=ax, color=colors, edgecolor="black", alpha=0.85)
ax.set_title("Distribución de personalidades en todos los agentes", fontsize=14)
ax.set_xlabel("Rasgo"); ax.set_ylabel("Cantidad de agentes")
ax.tick_params(axis="x", rotation=30)
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/01_distribucion_personalidades.png", dpi=150)
plt.close()
print(f"  -> Guardado: 01_distribucion_personalidades.png")


# ══════════════════════════════════════════════════════════════
#  3. DINÁMICA DE NECESIDADES POR RASGO
# ══════════════════════════════════════════════════════════════
if needs is not None:
    section("3. DINÁMICA DE NECESIDADES POR RASGO")

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    need_cols = ["hunger","energy","hygiene","social"]
    need_labels = ["Hambre","Energía","Higiene","Social"]

    for ax, col, lbl in zip(axes.flat, need_cols, need_labels):
        for trait, grp in needs.groupby("trait"):
            mean_by_time = grp.groupby("sim_time")[col].mean()
            ax.plot(mean_by_time.index, mean_by_time.values,
                    label=trait, color=TRAIT_COLORS.get(trait,"#888"), alpha=0.8)
        ax.axhline(20, color="red",    linestyle="--", linewidth=0.8, alpha=0.5, label="Crítico")
        ax.axhline(40, color="orange", linestyle="--", linewidth=0.8, alpha=0.5, label="Bajo")
        ax.set_title(lbl); ax.set_xlabel("Tiempo (s)"); ax.set_ylabel("Nivel (0-100)")
        ax.legend(fontsize=7, ncol=2)

    plt.suptitle("Evolución promedio de necesidades por personalidad", fontsize=14)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/02_necesidades_por_rasgo.png", dpi=150)
    plt.close()
    print("  -> Guardado: 02_necesidades_por_rasgo.png")

    # Tabla resumen
    summary = needs.groupby("trait")[need_cols].agg(["mean","std"]).round(2)
    print(summary.to_string())


# ══════════════════════════════════════════════════════════════
#  4. RED SOCIAL DE INTERACCIONES
# ══════════════════════════════════════════════════════════════
if edges is not None:
    section("4. RED SOCIAL DE INTERACCIONES")

    # Identificar islas (nodos sin ninguna interacción)
    isolated = edges[edges["interaction_count"] == 0]
    active   = edges[edges["interaction_count"] >  0]
    print(f"  Pares que interactuaron: {len(active)}")
    print(f"  Pares sin interacción:   {len(isolated)}")

    # Construir grafo dirigido pesado
    G = nx.Graph()
    # Agregar todos los agentes únicos
    for _, row in agents.iterrows():
        G.add_node(row["agent_id"],
                   name=row["name"], trait=row["trait"])

    for _, row in active.iterrows():
        G.add_edge(row["agent_a_id"], row["agent_b_id"],
                   weight=row["interaction_count"])

    # Métricas de red
    degrees     = dict(G.degree(weight="weight"))
    isolated_nodes = [n for n, d in degrees.items() if d == 0]
    print(f"  Nodos aislados (sin interacción): {len(isolated_nodes)}")
    if len(G.nodes) > 1:
        try:
            density = nx.density(G)
            print(f"  Densidad del grafo: {density:.4f}")
        except Exception:
            pass

    # Comunidades por personalidad
    trait_isolation = {}
    for trait in agents["trait"].unique():
        trait_agents = set(agents[agents["trait"]==trait]["agent_id"])
        trait_isolated = [n for n in isolated_nodes if n in trait_agents]
        trait_isolation[trait] = len(trait_isolated) / max(len(trait_agents), 1)
    print("\n  Tasa de aislamiento por personalidad:")
    for t, rate in sorted(trait_isolation.items(), key=lambda x: -x[1]):
        print(f"    {t:14s}: {rate:.1%}")

    # Visualización de red
    fig, ax = plt.subplots(figsize=(14, 10))
    pos = nx.spring_layout(G, seed=42, k=2.5)
    node_colors = [TRAIT_COLORS.get(G.nodes[n].get("trait",""), "#888") for n in G.nodes]
    node_sizes  = [max(100, degrees.get(n,0)*40) for n in G.nodes]
    edge_widths = [G[u][v]["weight"] * 0.8 for u,v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=node_sizes, alpha=0.85, ax=ax)
    nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.4,
                           edge_color="#aaa", ax=ax)
    nx.draw_networkx_labels(G, pos,
                            labels={n: G.nodes[n].get("name","")[:6] for n in G.nodes},
                            font_size=7, ax=ax)

    # Leyenda de colores por rasgo
    for trait, col in TRAIT_COLORS.items():
        ax.scatter([], [], c=col, label=trait, s=80)
    ax.legend(fontsize=9, loc="upper left", title="Personalidad")
    ax.set_title("Red social de interacciones entre agentes\n"
                 "(tamaño = número de interacciones, grosor = peso del borde)", fontsize=13)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/03_red_social.png", dpi=150)
    plt.close()
    print("  -> Guardado: 03_red_social.png")

    # Heatmap de interacciones entre rasgos
    if convs is not None:
        pivot = (convs.groupby(["initiator_trait","responder_trait"])
                      .size().unstack(fill_value=0))
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(pivot, annot=True, fmt="d", cmap="YlGnBu",
                    linewidths=0.5, ax=ax)
        ax.set_title("Interacciones entre rasgos\n(filas = iniciador, columnas = receptor)",
                     fontsize=13)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/04_heatmap_rasgos.png", dpi=150)
        plt.close()
        print("  -> Guardado: 04_heatmap_rasgos.png")


# ══════════════════════════════════════════════════════════════
#  5. ANÁLISIS DE SENTIMIENTO POR RASGO
# ══════════════════════════════════════════════════════════════
if utts is not None:
    section("5. ANÁLISIS DE SENTIMIENTO POR RASGO")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    sent_cols  = ["polarity","aggression","curiosity"]
    sent_lbls  = ["Polaridad (negativo→positivo)",
                  "Agresividad","Curiosidad"]

    for ax, col, lbl in zip(axes, sent_cols, sent_lbls):
        trait_vals = {}
        for trait in utts["speaker_trait"].unique():
            vals = utts[utts["speaker_trait"]==trait][col].dropna().values
            if len(vals): trait_vals[trait] = vals

        bp = ax.boxplot(
            [trait_vals.get(t, [0]) for t in trait_vals],
            labels=list(trait_vals.keys()),
            patch_artist=True,
            medianprops={"color":"black","linewidth":2},
        )
        for patch, trait in zip(bp["boxes"], trait_vals.keys()):
            patch.set_facecolor(TRAIT_COLORS.get(trait, "#888"))
        ax.set_title(lbl, fontsize=11)
        ax.tick_params(axis="x", rotation=35)

    plt.suptitle("Distribución de métricas de sentimiento por personalidad",
                 fontsize=13)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/05_sentimiento_por_rasgo.png", dpi=150)
    plt.close()
    print("  -> Guardado: 05_sentimiento_por_rasgo.png")

    # Tabla resumen
    sent_summary = (utts.groupby("speaker_trait")[sent_cols]
                       .agg(["mean","std"]).round(4))
    print(sent_summary.to_string())


# ══════════════════════════════════════════════════════════════
#  6. ML: PREDICCIÓN DE RASGO A PARTIR DE COMPORTAMIENTO
# ══════════════════════════════════════════════════════════════
if needs is not None and len(needs) > 30:
    section("6. ML: PREDICCIÓN DE RASGO (Random Forest + MLP)")

    # Features por agente: estadísticas de sus necesidades + eventos
    feat_needs = (needs.groupby(["agent_id","trait"])[
        ["hunger","energy","hygiene","social","need_deficit"]
    ].agg(["mean","std","min","max"]))
    feat_needs.columns = ["_".join(c) for c in feat_needs.columns]
    feat_needs = feat_needs.reset_index()

    if states is not None:
        # Frecuencia de estados por agente
        state_freq = (states.groupby(["agent_id","to_state"])
                            .size().unstack(fill_value=0))
        feat_needs = feat_needs.merge(state_freq, on="agent_id", how="left")

    feat_needs = feat_needs.fillna(0)
    le = LabelEncoder()
    y  = le.fit_transform(feat_needs["trait"])
    X  = feat_needs.drop(columns=["agent_id","trait"]).values

    if len(X) >= 10:
        sc   = StandardScaler()
        X_sc = sc.fit_transform(X)

        # Random Forest
        rf = RandomForestClassifier(n_estimators=200, random_state=42)
        cv_rf = cross_val_score(rf, X_sc, y, cv=min(5, len(X)//2), scoring="accuracy")
        print(f"  Random Forest CV accuracy: {cv_rf.mean():.3f} ± {cv_rf.std():.3f}")

        # Red Neuronal (MLP)
        mlp = MLPClassifier(hidden_layer_sizes=(64,32), max_iter=500,
                            random_state=42, early_stopping=True)
        cv_mlp = cross_val_score(mlp, X_sc, y, cv=min(5, len(X)//2), scoring="accuracy")
        print(f"  MLP Neural Net CV accuracy: {cv_mlp.mean():.3f} ± {cv_mlp.std():.3f}")

        # Feature importance (RF)
        rf.fit(X_sc, y)
        importances = pd.Series(rf.feature_importances_,
                                index=feat_needs.drop(columns=["agent_id","trait"]).columns)
        top_feat = importances.nlargest(15)
        fig, ax = plt.subplots(figsize=(10, 5))
        top_feat.sort_values().plot(kind="barh", ax=ax, color="#4CAF50", edgecolor="black")
        ax.set_title("Top 15 features para predecir personalidad\n(Random Forest importance)",
                     fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/06_feature_importance.png", dpi=150)
        plt.close()
        print("  -> Guardado: 06_feature_importance.png")

        # Confusion matrix del mejor modelo
        X_tr, X_te, y_tr, y_te = train_test_split(X_sc, y, test_size=0.25,
                                                    random_state=42, stratify=y if len(np.unique(y)) < len(y)//2 else None)
        rf.fit(X_tr, y_tr)
        y_pred = rf.predict(X_te)
        if len(y_te) > 0:
            cm = confusion_matrix(y_te, y_pred)
            fig, ax = plt.subplots(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                        xticklabels=le.classes_, yticklabels=le.classes_, ax=ax)
            ax.set_title("Matriz de confusión – Predicción de rasgo", fontsize=12)
            ax.set_xlabel("Predicho"); ax.set_ylabel("Real")
            plt.tight_layout()
            plt.savefig(f"{OUTPUT_DIR}/07_confusion_matrix.png", dpi=150)
            plt.close()
            print("  -> Guardado: 07_confusion_matrix.png")
            print(classification_report(y_te, y_pred, target_names=le.classes_, zero_division=0))
    else:
        print("  [SKIP] Necesitas mas datos (agentes) para ML supervisado.")


# ══════════════════════════════════════════════════════════════
#  7. CLUSTERING: PERFILES CONDUCTUALES
# ══════════════════════════════════════════════════════════════
if needs is not None and len(needs) > 20:
    section("7. CLUSTERING: PERFILES CONDUCTUALES (K-Means + t-SNE)")

    feat_cluster = (needs.groupby("agent_id")[
        ["hunger","energy","hygiene","social","need_deficit"]
    ].agg(["mean","std"])).reset_index()
    feat_cluster.columns = ["_".join(c) if c[1] else c[0]
                            for c in feat_cluster.columns]
    feat_cluster = feat_cluster.fillna(0)
    trait_map    = agents.set_index("agent_id")["trait"].to_dict()
    feat_cluster["trait"] = feat_cluster["agent_id"].map(trait_map)

    X_cl = feat_cluster.drop(columns=["agent_id","trait"]).values
    sc2  = StandardScaler()
    X_sc2 = sc2.fit_transform(X_cl)

    best_k, best_sil = 2, -1
    for k in range(2, min(9, len(X_cl))):
        km  = KMeans(n_clusters=k, random_state=42, n_init=10)
        lbl = km.fit_predict(X_sc2)
        sil = silhouette_score(X_sc2, lbl)
        if sil > best_sil:
            best_k, best_sil = k, sil
    print(f"  K óptimo: {best_k}  (silhouette={best_sil:.3f})")

    km   = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    clus = km.fit_predict(X_sc2)
    feat_cluster["cluster"] = clus

    # t-SNE para visualización 2D
    if len(X_sc2) >= 5:
        perp = min(30, len(X_sc2)//2)
        tsne = TSNE(n_components=2, perplexity=perp, random_state=42)
        emb  = tsne.fit_transform(X_sc2)

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        # Por cluster
        scatter_c = axes[0].scatter(emb[:,0], emb[:,1], c=clus,
                                     cmap="tab10", s=60, alpha=0.8)
        plt.colorbar(scatter_c, ax=axes[0])
        axes[0].set_title(f"t-SNE – Clusters conductuales (K={best_k})", fontsize=12)

        # Por rasgo
        trait_list = feat_cluster["trait"].fillna("desconocido")
        le2 = LabelEncoder(); trait_enc = le2.fit_transform(trait_list)
        scatter_t = axes[1].scatter(emb[:,0], emb[:,1], c=trait_enc,
                                     cmap="tab20", s=60, alpha=0.8)
        for i, (x, y_pos) in enumerate(emb):
            name = agents.set_index("agent_id")["name"].get(
                feat_cluster["agent_id"].iloc[i], "")
            axes[1].annotate(name[:5], (x, y_pos), fontsize=6, alpha=0.6)
        axes[1].set_title("t-SNE – Coloreado por rasgo real", fontsize=12)

        plt.suptitle("Espacio de comportamiento de agentes (t-SNE)", fontsize=13)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/08_tsne_clusters.png", dpi=150)
        plt.close()
        print("  -> Guardado: 08_tsne_clusters.png")

        # Tabla de rasgos por cluster
        cross = pd.crosstab(feat_cluster["cluster"], feat_cluster["trait"])
        print("\n  Composición de clusters por rasgo:")
        print(cross.to_string())


# ══════════════════════════════════════════════════════════════
#  8. PREDICCIÓN DE POLARIDAD DE DIÁLOGO (NN regresora)
# ══════════════════════════════════════════════════════════════
if utts is not None and len(utts) > 30:
    section("8. REGRESIÓN NEURAL: PREDICCIÓN DE POLARIDAD DEL DIÁLOGO")

    le_t = LabelEncoder()
    utts["speaker_trait_enc"]  = le_t.fit_transform(utts["speaker_trait"].fillna("desconocido"))
    utts["listener_trait_enc"] = le_t.transform(
        utts["listener_trait"].fillna("desconocido").apply(
            lambda x: x if x in le_t.classes_ else le_t.classes_[0]))

    feat_cols = ["speaker_trait_enc","listener_trait_enc",
                 "word_count","lexical_richness","questions","exclamations",
                 "speaker_hunger","speaker_energy","speaker_hygiene","speaker_social",
                 "turn_index","aggression","curiosity"]
    target = "polarity"

    df_ml = utts[feat_cols + [target]].dropna()
    if len(df_ml) >= 20:
        X2 = df_ml[feat_cols].values
        y2 = df_ml[target].values
        sc3 = StandardScaler()
        X2s = sc3.fit_transform(X2)

        mlp_r = MLPRegressor(hidden_layer_sizes=(64,32,16), max_iter=1000,
                             random_state=42, early_stopping=True)
        cv_r = cross_val_score(mlp_r, X2s, y2, cv=min(5, len(X2)//5),
                               scoring="r2")
        print(f"  MLP Regressor – R² (polaridad): {cv_r.mean():.4f} ± {cv_r.std():.4f}")

        # Scatter predicho vs real
        mlp_r.fit(X2s, y2)
        y_pred_r = mlp_r.predict(X2s)
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.scatter(y2, y_pred_r, alpha=0.5, s=20, color="#00BCD4")
        lims = [min(y2.min(), y_pred_r.min()), max(y2.max(), y_pred_r.max())]
        ax.plot(lims, lims, "r--", linewidth=1.5)
        ax.set_xlabel("Polaridad real"); ax.set_ylabel("Polaridad predicha")
        ax.set_title(f"Predicción de polaridad (MLP) – R²={cv_r.mean():.3f}", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/09_prediccion_polaridad.png", dpi=150)
        plt.close()
        print("  -> Guardado: 09_prediccion_polaridad.png")
    else:
        print("  [SKIP] Necesitas mas turnos de dialogo para este analisis.")


# ══════════════════════════════════════════════════════════════
#  9. ISLAS SOCIALES
# ══════════════════════════════════════════════════════════════
if edges is not None:
    section("9. ISLAS SOCIALES (agentes sin interacciones)")

    all_agents = set(agents["agent_id"].unique())
    agents_with_interactions = set(
        edges[edges["interaction_count"] > 0]["agent_a_id"].tolist() +
        edges[edges["interaction_count"] > 0]["agent_b_id"].tolist()
    )
    islands = all_agents - agents_with_interactions
    print(f"  Total agentes: {len(all_agents)}")
    print(f"  Con interacciones: {len(agents_with_interactions)}")
    print(f"  Sin interacciones (islas): {len(islands)}")

    if islands:
        island_df = agents[agents["agent_id"].isin(islands)][["name","trait","backstory"]]
        print("\n  Agentes aislados:")
        print(island_df.to_string(index=False))

        island_traits = agents[agents["agent_id"].isin(islands)]["trait"].value_counts()
        total_traits  = agents["trait"].value_counts()
        isolation_rate = (island_traits / total_traits).fillna(0).sort_values(ascending=False)
        print("\n  Tasa de aislamiento por rasgo:")
        print(isolation_rate.to_string())

        fig, ax = plt.subplots(figsize=(9, 4))
        isolation_rate.plot(kind="bar", ax=ax,
                            color=[TRAIT_COLORS.get(t,"#888") for t in isolation_rate.index],
                            edgecolor="black", alpha=0.85)
        ax.set_title("Tasa de aislamiento social por personalidad", fontsize=12)
        ax.set_ylabel("Proporción de agentes aislados")
        ax.tick_params(axis="x", rotation=30)
        ax.axhline(0.5, color="red", linestyle="--", alpha=0.5, label="50%")
        ax.legend()
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/10_islas_sociales.png", dpi=150)
        plt.close()
        print("  -> Guardado: 10_islas_sociales.png")


# ══════════════════════════════════════════════════════════════
#  10. RESUMEN FINAL
# ══════════════════════════════════════════════════════════════
section("10. RESUMEN")

files = sorted(os.listdir(OUTPUT_DIR))
print(f"\n  Archivos generados en '{OUTPUT_DIR}/':")
for f in files:
    size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
    print(f"    {f:45s}  {size//1024:4d} KB")

print(f"\n  Datos fuente en '{DATA_DIR}/':")
for f in sorted(os.listdir(DATA_DIR)):
    p = os.path.join(DATA_DIR, f)
    size = os.path.getsize(p)
    print(f"    {f:45s}  {size//1024:4d} KB")

print("\n  Analisis completado.")
