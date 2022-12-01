import pandas as pd
import datetime
import re
import matplotlib.pyplot as plt
import seaborn as sns
import os
import warnings

warnings.filterwarnings("ignore")

def compilar_patrones():
    espacio = re.compile(r'\s')
    guion = re.compile(r'-')
    arroba = re.compile(r'@')
    d_0 = re.compile(r'0')
    d_3 = re.compile(r'3')
    uno = re.compile(r'one',re.I)
    dos = re.compile(r'two',re.I)
    comma = re.compile(r',')
    
    quitar = [espacio, guion, arroba, d_0, d_3, uno, dos,]
    poner = ['_', '_', 'a', 'o', 'e', '1', '2']
    patrones = [quitar, poner, comma]
    return patrones

def drop_nans(df_orders:pd.DataFrame, df_order_details:pd.DataFrame):
    """
    Dropeamos los NaNs de ambos dataframes. Intersecamos ambos dataframes
    para droppear lo que hemos sacado de un dataframe en el otro
    """
    df_order_details.dropna(inplace=True)
    or_id_A = set(df_orders['order_id'].unique())
    or_id_B = set(df_order_details['order_id'].unique())
    keep_order_id = or_id_A & or_id_B
    df_orders = df_orders[df_orders['order_id'].isin(keep_order_id)]
    df_order_details = df_order_details[df_order_details['order_id'].isin(keep_order_id)]
    # Ordenamos los Dataframes y reiniciamos sus índices
    df_orders.sort_values(by='order_id', inplace=True)
    df_orders.reset_index(drop=True, inplace=True)
    df_order_details.sort_values(by='order_id', inplace=True)
    df_order_details.reset_index(drop=True, inplace=True)
    return df_orders, df_order_details


def extract():
    file_names = ['data_dictionary.csv', 'order_details.csv', 'orders.csv', 'pizza_types.csv','pizzas.csv']
    df_lst = []
    for name in file_names:
        if name in ['data_dictionary.csv','pizzas.csv','pizza_types.csv']:
            sep = ','
        else:
            sep = ';'
        df = pd.read_csv(f'files2016/{name}', sep, encoding='latin_1')
        df_lst.append(df)
    return df_lst


def limpieza_de_datos(df_orders:pd.DataFrame, df_order_details:pd.DataFrame):
    ### LIMPIEZA DE LOS DATOS
    ## 1. FORMATO DATETIME
    for i in range(len(df_orders)):
        unformatted_date = str(df_orders['date'][i])
        df_orders.loc[i,'date'] = pd.to_datetime(df_orders['date'][i], errors='coerce')
        if pd.isnull(df_orders.loc[i,'date']):
            unformatted_date = unformatted_date[:unformatted_date.find('.')]
            formatted_date = datetime.datetime.fromtimestamp(int(unformatted_date))
            df_orders.loc[i,'date'] = pd.to_datetime(formatted_date)

    df_orders['date'] = pd.to_datetime(df_orders['date'], format="%Y/%m/%d")
    df_orders['week'] = df_orders['date'].dt.week
    df_orders['weekday'] = df_orders['date'].dt.weekday

    ## 2. CORREGIR NOMBRES

    df_orders, df_order_details = drop_nans(df_orders, df_order_details)
    patrones = compilar_patrones()
    [quitar, poner, comma] = patrones
    # Ahora debo corregir los nombres de las pizzas y los números
    for i in range(len(quitar[:-2])):
        df_order_details['pizza_id'] = [quitar[i].sub(poner[i], str(x)) for x in df_order_details['pizza_id']]
    for i in range(len(quitar[:-2]), len(quitar)):
        df_order_details['quantity'] = [quitar[i].sub(poner[i], str(x)) for x in df_order_details['quantity']]
    df_order_details['quantity'] = [abs(int(x)) for x in df_order_details['quantity']]

    return df_orders, df_order_details, comma


def transform(df_lst: list[pd.DataFrame], semana: str):
    df_orders = df_lst[2]
    df_order_details = df_lst[1]
    df_orders.dropna(inplace=True)
    df_orders.reset_index(drop=True, inplace=True)
    df_orders.drop('time', axis=1, inplace=True)

    df_orders, df_order_details, comma = limpieza_de_datos(df_orders, df_order_details)

    ### OBTENER PREDICCIÓN
    ## 1. OBTENER DF DE SEMANA ANTERIOR, ACTUAL Y POSTERIOR Y SUMARLAS PONDERADAMENTE
    pizzas_df = df_lst[4]
    pizzas_dict = {}
    for index in range(len(pizzas_df)):
        pizzas_dict[pizzas_df['pizza_id'][index]] = 0

    # Esta es la semana que hemos escogido. Se puede cambiar la semana aquí
    for week in range(-1,2):
        # Vamos elegir una semana
        for i in range(len(df_orders)):
            if df_orders['date'][i].week == semana - 1 + week:
                init = i+1  #df_orders['order_id'][i]
            if df_orders['date'][i].week == semana + week:
                end = i+1  #df_orders['order_id'][i]
        
        for i in range(len(df_order_details)):
            if df_order_details['order_id'][i] == init:
                init_order_details = i
            if df_order_details['order_id'][i] == end:
                end_order_details = i + 1

        week_df = df_order_details.iloc[init_order_details:end_order_details]
        week_df['quantity'] = week_df['quantity'].astype('int64')
        ##########################################
        # Ahora vamos a contar las pizzas que se han pedido en esa semana
        # Primero creamos un diccionario cuyas claves sean todos los tipos
        # de pizzas y cuyos respectivos valores sea el número de veces que
        # se ha pedido cada pizza
        
        week_df.reset_index(drop=True)

        # Damos un peso diferente a cada semana: 0.3, 0.4 y 0.3 (anterior,
        # actual y siguiente)
        
        if week in [-1,1]:
            for index in range(1,len(week_df)):
                # Así accedemos a un valor concreto: df.iloc[columna].iloc[fila]
                pizzas_dict[week_df['pizza_id'].iloc[index]] += 0.3*week_df['quantity'].iloc[index]
        else:
            for index in range(1,len(week_df)):
                # Así accedemos a un valor concreto: df.iloc[columna].iloc[fila]
                pizzas_dict[week_df['pizza_id'].iloc[index]] += 0.4*week_df['quantity'].iloc[index]
    
    # Ahora redondeamos todo el dataframe
    for key in pizzas_dict.keys():
        pizzas_dict[key] = round(pizzas_dict[key])
    
    # Una vez tenemos las pizzas necesarias, tenemos que obtener los ingredientes
    comma = re.compile(r',')
    espacio = re.compile(r'\s')
    pizza_types_df = df_lst[3]

    ingredients_dict = {}
    for pizza1_ingredients in pizza_types_df['ingredients']:
        pizza1_ingredients = espacio.sub('',pizza1_ingredients)
        ingredients = comma.split(pizza1_ingredients)
        for ingredient in ingredients:
            if ingredient not in ingredients_dict:
                ingredients_dict[ingredient] = 0
    
    for key in pizzas_dict:
        if key[-1] == 's':
            end_str, count = 2, 0.75
        elif key[-1] == 'm':
            end_str, count = 2, 1
        elif key[-1] == 'l' and key[-2] != 'x':
            end_str, count = 2, 1.5
        elif key[-2:] == 'xl' and key[-3] != 'x': # xl
            end_str, count = 3, 2
        else: # xxl
            end_str, count = 4, 3
        
        pizza = key[:-end_str]
        current_pizza_ingredients = pizza_types_df[pizza_types_df['pizza_type_id'] == pizza]["ingredients"].head(1).item()
        current_pizza_ingredients = espacio.sub('',current_pizza_ingredients)
        ingredients_lst = comma.split(current_pizza_ingredients)
        
        for ingredient in ingredients_lst:
            ingredients_dict[ingredient] += count

    # Multiplicamos el diccionario por 1.2 para tener un margen de ingredientes
    # y redondeamos el resultado (ya que no podemos tener fracciones de ingredientes)
    for key in ingredients_dict.keys():
        ingredients_dict[key] = round(ingredients_dict[key]*1.2)

    return ingredients_dict

def load(ingredients_dict: dict, semana: str):
    series_ingredients_week = pd.DataFrame({0: ingredients_dict})
    if not os.path.exists(f'ingredients_week_{semana}.csv'):
        series_ingredients_week.to_csv(f'ingredients_week_{semana}.csv')
    
    series_ingredients_week.columns = ["quantity"]
    series_ingredients_week["ingredients"] = series_ingredients_week.index
    series_ingredients_week.index = range(series_ingredients_week.shape[0])

    # Visualizar los datos
    plt.figure(figsize=(12,6))
    plt.title("Feature importance")
    ax = sns.barplot(x='ingredients', y='quantity', data=series_ingredients_week,palette='rocket_r')
    plt.xticks(rotation=90)
    plt.show()

if __name__ == "__main__":
    df_lst = extract()
    semana = 25
    pizzas_dict = transform(df_lst, semana)
    load(pizzas_dict, semana)