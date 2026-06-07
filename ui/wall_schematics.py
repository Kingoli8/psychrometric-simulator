import streamlit as st
import plotly.graph_objects as go

min_visual_thickness = 0.01  # Minimum thickness in meters for visual purposes

def draw_wall_layers(plot_df, unique_key):
    """
    Draws an interactive 1D schematic of the wall layers using Plotly.
    Enforces a minimum visual thickness so microscopic films/gaps remain clickable.
    """
    fig = go.Figure()

    for idx, row in plot_df.iterrows():
        # The exact mathematical thickness
        true_thickness = float(row['Thickness (m)'])
        
        # --- NEW: The Artificial Visual Thickness ---
        # If true_thickness is tiny (like 1e-5), Plotly will draw it as 0.01
        display_thickness = max(true_thickness, min_visual_thickness)
        
        material = row['Material']
        color = row['Color']

        # The hover text ONLY shows the true math
        hover_html = (
            f"<b>{material}</b><br>"
            f"Thickness: {true_thickness:.4g} m<br>"
            "<extra></extra>" 
        )

        fig.add_trace(go.Bar(
            y=['Wall Section'], 
            x=[display_thickness], # We feed Plotly the artificial size
            name=material,
            text=material, 
            textposition='inside',
            insidetextanchor='middle',
            orientation='h',
            marker=dict(
                color=color, 
                line=dict(color='rgba(0,0,0,0.5)', width=2)
            ),
            hovertemplate=hover_html
        ))

    fig.update_layout(
        barmode='stack',
        height=180, 
        margin=dict(l=0, r=0, t=10, b=10),
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        dragmode='pan'
    )
    
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d']
    }

    st.plotly_chart(fig, width='stretch', config=config, key=unique_key)