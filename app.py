import dash
from dash import dcc
from dash import html
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import pandas.io.sql as sqlio
from fetch_data_from_db import *

## READ COVID DATA FROM OWID REPO
df_h, df_latest = fetch_entire_tables()
#print(df_h.shape, df_h.head())
#print(df_latest.shape, df_latest.head())
hist_feats = df_h.columns
#print(hist_feats)
latest_feats = df_latest.columns
## Determining if feature is continuous
THRESH = 0.01
def is_cont(data, cat_name):
    if data[cat_name].dtype != 'float64':
        return False
    if data[cat_name].nunique() / data[cat_name].count() < THRESH:
        return False
    return True
    

# Definitions of constants. This projects uses extra CSS stylesheet at `./assets/style.css`
COLORS = ['rgb(67,67,67)', 'rgb(115,115,115)', 'rgb(49,130,189)', 'rgb(189,189,189)']
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css', '/assets/style.css']

# Define the dash app first
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


# Define component functions
def xy_plot():
    return html.Div(children=[
        html.Div(children=[
            html.H2(children='Target Variable Visualization'),
            dcc.Dropdown(
                id='x_feature_dd',
                options=[{'label': col, 'value': col} for col in df_latest.columns],
                multi=False,
                placeholder='Feature to Plot Over',
                value=df_latest.columns[0]
            ),
            dcc.Dropdown(
                id='y_feature_dd',
                options=[{'label': col, 'value': col} for col in df_latest.columns],
                multi=False,
                placeholder='Feature to Plot Over',
                value=df_latest.columns[6]
            ),
            html.Div(children=[
                dcc.Graph(id='xy_fig')]),
        ])
    ], className='row')


def timeline_comparator():
    return html.Div(children=[
        html.Div(children=[
            html.H2("Compare Trends of a Target for a Value"),
            dcc.Dropdown(
                id='feature_dd',
                options=[{'label': f, 'value': f} for f in hist_feats if df_h[f].dtype == 'object'],
                multi=False,
                placeholder='Historical Feature to Visualize',
                value='new_cases_smoothed'
            ),
            dcc.Dropdown(
                id='filter_feat_dd',
                options=[{'label': f, 'value': f} for f in hist_feats if df_h[f].dtype == 'object'],
                multi=False,
                placeholder='Feature to Filter',
                value='location'
            ),
            dcc.Dropdown(
                id='filter_val_dd',
                options=[],
                multi=True,
                placeholder='Value(s) to Filter By',
                value=[df_h.iloc[0]['location'],df_h.iloc[3]['location']] 
            ),
            html.Div(children=[
                dcc.Graph(id='timeline_fig')])
            ])
    ])

def line_graph():
    if df_h is None:
        return go.Figure()
    dynamic_feats = ['icu_patients_per_million', 'new_cases', 'total_vaccinations_per_hundred', 'total_deaths_per_million']
    x_coord = df_h['date']
    display_fig = go.Figure()
    for index, feats in enumerate(dynamic_feats):
        display_fig.add_trace(go.Scatter(x=x_coord, y=df_h[feats], mode='lines', name=feats,
                                 line={'width': 2, 'color': COLORS[index]}))
    display_fig.add_trace(go.Scatter(x=x_coord, y=df_h['total_cases'], mode='lines', name='total_cases',
                             line={'width': 2, 'color': 'red'}))
    title = 'Line Graph Feature Comparison Relative to Data VS Total Cases'
    display_fig.update_layout(template='plotly',
                      title=title,
                      plot_bgcolor='#D3D3D3',
                      paper_bgcolor='#D3D3D3',
                      yaxis_title='Total_Cases',
                      xaxis_title='Date')
    return display_fig


# Sequentially add page components to the app's layout
def dynamic_layout():
    return html.Div([
        xy_plot(),
        timeline_comparator(),
        dcc.Graph(id='line-graph-comparison', figure=line_graph()),
    ], className='row', id='content')


# set layout to a function which updates upon reloading
app.layout = dynamic_layout


# Defines the dependencies of interactive components

# Updating Target Variable (new_cases) Visualization for Latest Data
@app.callback(
    dash.dependencies.Output('xy_fig', 'figure'),
    [dash.dependencies.Input('x_feature_dd', 'value'),
    dash.dependencies.Input('y_feature_dd', 'value')]
)
def update_xy_plot(feature_name, target_var):
    #target_var = 'new_cases_smoothed'
    fig = None
    if feature_name != target_var:
        if is_cont(df_latest, feature_name):
            fig = px.scatter(df_latest, x=feature_name, y=target_var, 
                             title=f"Scatter {target_var} over {feature_name}")
        else:
            fig = px.bar(df_latest, x = feature_name, y= target_var,
                         title=f"BoxPlot {target_var} over {feature_name}")

    fig.update_layout(template='plotly', title=f'Visualizing {target_var} v. {feature_name} for Latest Data',
                          plot_bgcolor='#D3D3D3', paper_bgcolor='#D3D3D3')
    return fig


# Updating Historical Data Visualization
@app.callback(
    [dash.dependencies.Output('filter_val_dd', 'options'),
     dash.dependencies.Output('filter_val_dd', 'value')],
    dash.dependencies.Input('filter_feat_dd', 'value')
)
def update_filter_val_options(filter_feat):
    not_null_mask = df_h[filter_feat].notnull()
    unique_vals = df_h[filter_feat][not_null_mask].unique()
    options = [{'label': val, 'value': val} for val in unique_vals]
    value = options[0]['value']
    return options, value


@app.callback(
    dash.dependencies.Output('timeline_fig', 'figure'),
    [dash.dependencies.Input('feature_dd', 'value'),
     dash.dependencies.Input('filter_feat_dd', 'value'),
     dash.dependencies.Input('filter_val_dd', 'value')]
)
def update_timeline_comparator(plot_feature, filter_feature, filter_value):
    hist_time_feature = 'date' # can put in db_info
    toPlot = []
    for v in filter_value:
        #print(v)
        hist_filter_mask = df_h[filter_feature] == v
        df_filtered = df_h[hist_filter_mask]
        df_filtered = df_filtered.sort_values(by=[hist_time_feature], axis=0)
        toPlot.append(df_filtered)

    fig = go.Figure()
    for i, filtered in enumerate(toPlot):
        fig.add_trace(go.Scatter(x=df_h[hist_time_feature],y=filtered[plot_feature], mode="markers", name=str(filter_value[i])))

    fig.update_layout(template='plotly', title=f'Historical Timeline of {plot_feature} Over {filter_feature} for Selected Values',
                          plot_bgcolor='#D3D3D3', paper_bgcolor='#D3D3D3')
    return fig




if __name__ == '__main__':
    app.run_server(debug=True, port=1050, host='0.0.0.0')