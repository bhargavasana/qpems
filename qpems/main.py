
from os.path import join, dirname
import pandas as pd
from bokeh.io import curdoc
from bokeh.layouts import row, column
from bokeh.models import (ColumnDataSource, DataRange1d, Select, DatetimeTickFormatter, Circle,
                          CustomJS, WMTSTileSource, Range1d, 
                          HoverTool, PanTool, WheelZoomTool, BoxZoomTool, ResetTool, TapTool)
from bokeh.models.widgets import Button
from bokeh.plotting import figure


monstr_dict = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
             7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
strmon_dict = {v: k for k, v in monstr_dict.iteritems()}
dow_dict = {1:'Avg_Wkday',2:'Avg_Wkday',3:'Avg_Wkday',5:'Sat',6:'Sun'}
TOOLS = "pan,wheel_zoom,box_zoom,reset,save"

STAMEN_TERRAIN = WMTSTileSource(
    url='http://tile.stamen.com/terrain/{Z}/{X}/{Y}.png',
    attribution=(
        'Map tiles by <a href="http://stamen.com">Stamen Design</a>, '
        'under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>.'
        'Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, '
        'under <a href="http://www.openstreetmap.org/copyright">ODbL</a>'
    )
)

def get_monyr(x):
    m,y = x.split(',')
    m = strmon_dict[m]
    y = int(y)
    return m, y

def compare_monyrval(fm_val, to_val):
    m,y = get_monyr(fm_val)
    m2,y2 = get_monyr(to_val)
    return m2>=m and y2>=y

def get_monyropt(fm_val):
    retval = [x for x in monyr_options if compare_monyrval(fm_val, x)]
    return retval

infile = join(dirname(__file__), 'data/pems_data.h5')
def get_dataset(sta, fm_date, to_date, tp):
    sta = int(sta)
    fm_mon, fm_year = get_monyr(fm_date)
    to_mon, to_year = get_monyr(to_date)

    df = pd.read_hdf(infile, 'data', where='Station=%s' %sta)
    df['dti'] = pd.to_datetime(df['Timestamp'], format ="%m/%d/%Y %H:%M:%S")
    df['mon'] = df['dti'].dt.month
    df['year'] = df['dti'].dt.year
    df = df.loc[(df['mon']>=fm_mon) & (df['year']>=fm_year) & (df['mon']<=to_mon) & (df['year']<=to_year),]
    df = df.set_index('dti')
    df = df['Total_Flow'].resample(tp).sum().reset_index()
    df['time'] = df['dti'].dt.time
    df['dow'] = df['dti'].dt.dayofweek # Monday=0, Sunday=6
    df = df.loc[df['dow'].isin([1,2,3,5,6]),]
    df['dow'] = df['dow'].map(dow_dict)
    df = df[['dow','time','Total_Flow']].groupby(['dow','time']).mean().reset_index()
    df = df.pivot(index='time',columns='dow',values='Total_Flow').reset_index()

    return ColumnDataSource(data=df)

mapselect_code = """
var sel_ind;
var inds = cb_obj.selected['1d'].indices;
var data = cb_obj.data;
if(inds.length == 0){
   cb_obj.selected['1d'].indices = [data.ID.indexOf(staselsrc.data['sta_id'][0])];
   console.log(staselsrc.data['sta_id'][0]);
   console.log(cb_obj.selected['1d'].indices);
   } else {
   cb_obj.selected['1d'].indices = inds.slice(0,1);
   console.log(cb_obj.selected['1d'].indices);
}
sel_ind = cb_obj.selected['1d'].indices;
mapselsrc.data['ID'][0] = cb_obj.data['ID'][sel_ind];
mapselsrc.data['x'][0] = cb_obj.data['x'][sel_ind];
mapselsrc.data['y'][0] = cb_obj.data['y'][sel_ind];

cb_obj.trigger('change');
mapselsrc.trigger('change');
"""

def get_mapsrcs(sta):
    nonsel = ColumnDataSource(data=station_detail[['ID','x','y']])
    sel = ColumnDataSource(data=station_detail.loc[station_detail['ID']==int(sta),['ID','x','y']].reset_index())
    return sel, nonsel
    
def mapselect_callback():
    if len(map_source.selected['1d']['indices']) > 0:
        sel_idx = map_source.selected['1d']['indices'][0]
        sel_sta = map_source.data['ID'][sel_idx]
        station_select.value = str(sel_sta)
        map_source.selected['1d']['indices'] = []
        map_source.trigger('data', map_source.data, map_source.data)

def make_plot(src, title=''):
    plot = figure(x_axis_type="datetime", plot_width=1000, tools=TOOLS)
    plot.title.text = title
    plot.title.text_font_size = '20pt'
    plot.title.text_font_style = 'bold'

    plot.line(x='time', y='Avg_Wkday', source=src, color='blue', legend='Avg. Wkday')
    plot.line(x='time', y='Sat', source=src, color='green', legend='Saturday')
    plot.line(x='time', y='Sun', source=src, color='red', legend='Sunday')

    hover = HoverTool(
        tooltips=[
            ("Hour", "$index"),
            ("Flow", "$y{0,0.0}"),
        ]
    )
    plot.add_tools(hover)

    # fixed attributes
    plot.xaxis.formatter = DatetimeTickFormatter(hours=['%H:%M'], days=['%H:%M'])
    plot.xaxis[0].ticker.desired_num_ticks = 24
    #plot.x_range = DataRange1d(range_padding=0.0)
    plot.xaxis.axis_label = 'Time of Day'
    plot.yaxis.axis_label = "Total Flow (Vehicles)"
    plot.legend.location = "bottom_right"

    gplot = figure(x_range=mapx_range, y_range=mapy_range, active_scroll=WheelZoomTool())
    gplot.axis.visible = False
    gplot.add_tile(STAMEN_TERRAIN)
    tptool = TapTool()
    gplot.add_tools(tptool)

    map_source.callback = CustomJS(args=dict(mapselsrc=map_selsource, staselsrc=station_select_source),code=mapselect_code)

    nonsel_circle = Circle(x="x", y="y", size=15, fill_color=None, line_color="blue")
    sel_circle = Circle(x="x", y="y", size=15, fill_color="red", line_color=None)
    highlight_circle = Circle(fill_color=None, line_color="blue")
    gplot.add_glyph(map_source, nonsel_circle, selection_glyph=highlight_circle, nonselection_glyph=highlight_circle)
    gplot.add_glyph(map_selsource, sel_circle)

    return plot, gplot

def update_plot(attrname, old, new):
    monyr_fm = monyr_from_select.value
    new_monyr_options = get_monyropt(monyr_fm)
    if monyr_to_select.value not in new_monyr_options:
        monyr_to_select.value = new_monyr_options[len(new_monyr_options)-1]
    monyr_to_select.options = new_monyr_options
    monyr_to = monyr_to_select.value
    sta = station_select.value
    timep = timep_select.value
    fwy, d, typ, lanes, name, lat, lon = get_sta_detail(sta)
    plot.title.text = "Vehicle Flow for Station %s: %s %s %s" %(sta,fwy,d,name)

    new_selsrc, new_nonselsrc = get_mapsrcs(sta)
    map_source.data.update(new_nonselsrc.data)
    map_selsource.data.update(new_selsrc.data)

    src = get_dataset(sta, monyr_fm, monyr_to, timep)
    source.data.update(src.data)

    patches = {'sta_id': [(0,int(station_select.value))]}
    station_select_source.patch(patches)

def get_sta_detail(sta):
    sel = station_detail.loc[station_detail['ID']==int(sta),]
    return sel['Fwy'].iloc[0], sel['Dir'].iloc[0], sel['Type'].iloc[0], sel['Lanes'].iloc[0],\
           sel['Name'].iloc[0], sel['Latitude'].iloc[0], sel['Longitude'].iloc[0]

def get_mapsta_index(src, sta):
    sta_series = src.data['ID']
    return sta_series[sta_series == int(sta)].index[0]

### Prepare month ,year selection items
monyr_df = pd.read_hdf(infile, 'monyr')
monyr_df['mon'] = monyr_df['m'].map(monstr_dict)
monyr_df['monyear'] = monyr_df['mon'] + ', ' + monyr_df['year'].astype(str)
monyr_options = monyr_df['monyear'].tolist()
monyr_from_select = Select(value=monyr_options[0], title='From', options=monyr_options)
monyr_to_select = Select(value=monyr_options[len(monyr_options)-1], title='To', options=monyr_options)

station_set = pd.read_hdf(infile, 'data', columns=['Station'])
station_detail = pd.read_hdf(infile, 'sta_detail')
# keep only stations that are both in count dataset and station detail
station_set = sorted(list(set(station_set['Station']).intersection(set(station_detail['ID']))))
station_set = map(str, station_set)
station_select = Select(value=station_set[0], title='Station List', options=station_set)
station_select_source = ColumnDataSource(data={'sta_id':[int(station_select.value)]})
timep_select = Select(value='1H', title='Time Aggregation', options=['15min','30min','1H'])

mapx_range = Range1d(start=station_detail['x'].min() - 30000, end=station_detail['x'].max() + 30000, bounds=None)
mapy_range = Range1d(start=station_detail['y'].min() - 20000, end=station_detail['y'].max() + 20000, bounds=None)
map_selsource, map_source = get_mapsrcs(station_set[0])
source = get_dataset(station_set[0], monyr_options[0], monyr_options[len(monyr_options)-1], '1H')
fwy, d, typ, lanes, name, lat, lon = get_sta_detail(station_set[0])
plot, gplot = make_plot(source, "Vehicle Flow for Station %s: %s %s %s" %(station_set[0],fwy,d,name))

button = Button(label="Select Station on Map and Click Here!", button_type="success")
button.on_click(mapselect_callback)

monyr_from_select.on_change('value', update_plot)
monyr_to_select.on_change('value', update_plot)
timep_select.on_change('value', update_plot)
station_select.on_change('value', update_plot)

date_range = row(monyr_from_select, monyr_to_select)
controls = column(row(station_select, timep_select), date_range, button)
layout = row(plot, column(controls, gplot))

curdoc().add_root(layout)
curdoc().title = "QPeMS (Quick PeMS: alpha version)"

