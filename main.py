import io
from fastapi import FastAPI, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import csv
import math
from openpyxl import load_workbook
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from database import engine, Base, init_db, get_db, Cliente, MetaMensal, ProdutoMeta, PositivacaoDinamica

# Geolocator setup using Nominatim
geolocator = Nominatim(user_agent="andina_pro_geocoder_v2")

def geocode_address(address_str):
    try:
        location = geolocator.geocode(address_str, timeout=3)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return None, None

def haversine_distance(lat1, lon1, lat2, lon2):
    r = 6371  # radius of Earth in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

def parse_float(val):
    try:
        if val is None:
            return None
        val_str = str(val).strip().replace(',', '.')
        return float(val_str) if val_str else None
    except ValueError:
        return None

app = FastAPI(title="Andina Pro")

# Initialize database

# Initialize database
init_db()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

def get_current_month():
    return datetime.now().strftime("%Y-%m")

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/config", response_class=HTMLResponse)
async def read_config(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})

@app.get("/metas", response_class=HTMLResponse)
async def read_metas(request: Request):
    return templates.TemplateResponse("metas.html", {"request": request})

@app.get("/cliente/{cod_cliente}", response_class=HTMLResponse)
async def read_cliente(request: Request, cod_cliente: str):
    return templates.TemplateResponse("cliente.html", {"request": request, "cod_cliente": cod_cliente})

# --- API ENDPOINTS ---

@app.post("/api/scan-routes")
async def scan_routes(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        filename = file.filename.lower()
        
        unique_routes = set()
        
        if filename.endswith('.xlsx'):
            wb = load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
            sheet = wb.active
            
            # Read first row
            headers_row = next(sheet.iter_rows(max_row=1, values_only=True), None)
            if not headers_row:
                return JSONResponse(status_code=400, content={"message": "Excel file is empty"})
                
            headers = [str(cell).strip() if cell is not None else '' for cell in headers_row]
            
            route_idx = None
            for idx, col in enumerate(headers):
                if col.strip().upper() == 'NOVA ROTA':
                    route_idx = idx + 1 # 1-based index for openpyxl
                    break
                    
            if route_idx is None:
                return JSONResponse(status_code=400, content={"message": "Não foi possível encontrar a coluna 'Nova Rota' na planilha Excel."})
                
            for row in sheet.iter_rows(min_row=2, min_col=route_idx, max_col=route_idx, values_only=True):
                if row:
                    val = str(row[0] or '').strip()
                    if val:
                        unique_routes.add(val)
        else:
            # Fallback to CSV
            content_str = contents.decode('utf-8-sig')
            dialect = csv.excel
            dialect.delimiter = ';'
            reader = csv.DictReader(io.StringIO(content_str), dialect=dialect)
            if reader.fieldnames:
                reader.fieldnames = [col.strip() for col in reader.fieldnames]
                
            route_col = None
            if reader.fieldnames:
                for col in reader.fieldnames:
                    if col.strip().upper() == 'NOVA ROTA':
                        route_col = col
                        break
                        
            if route_col is None:
                return JSONResponse(status_code=400, content={"message": "Não foi possível encontrar a coluna 'Nova Rota' na planilha CSV."})
                
            for row in reader:
                val = str(row.get(route_col) or '').strip()
                if val:
                    unique_routes.add(val)
                    
        return {"routes": sorted(list(unique_routes))}
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": f"Erro ao analisar rotas: {str(e)}"})

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...), rota: str = Form(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        filename = file.filename.lower()
        
        rows_to_process = []
        
        if filename.endswith('.xlsx'):
            wb = load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
            sheet = wb.active
            
            # Read first row
            headers_row = next(sheet.iter_rows(max_row=1, values_only=True), None)
            if not headers_row:
                raise HTTPException(status_code=400, detail="Excel file is empty")
            
            # Extract and clean headers
            headers = [str(cell).strip() if cell is not None else '' for cell in headers_row]
            print("COLUNAS ENCONTRADAS NO EXCEL:", headers)
            
            # Find the "Nova Rota" column index
            route_idx = None
            for idx, col in enumerate(headers):
                if col.strip().upper() == 'NOVA ROTA':
                    route_idx = idx
                    break
            if route_idx is None:
                raise HTTPException(status_code=400, detail="Coluna 'Nova Rota' não encontrada no Excel.")
                    # Map Excel columns dynamically
            header_map = {}
            for idx, col in enumerate(headers):
                col_upper = col.strip().upper()
                if col_upper.startswith('COD CLIEN') or col_upper.startswith('COD CLIENT') or ('COD' in col_upper and 'CLIEN' in col_upper):
                    header_map['cod_cliente'] = idx
                elif col_upper == 'RAZAO SOCIAL':
                    header_map['razao_social'] = idx
                elif col_upper == 'ENDERECO':
                    header_map['endereco'] = idx
                elif col_upper == 'BAIRRO':
                    header_map['bairro'] = idx
                elif col_upper == 'CIDADE':
                    header_map['cidade'] = idx
                elif col_upper == 'CANAL RESUMIDO':
                    header_map['canal_resumido'] = idx
                elif col_upper in ('CLASSIFICAC', 'CLASSIFICACAO'):
                    header_map['classificacao'] = idx
                elif col_upper == 'NOVO DIA':
                    header_map['novo_dia'] = idx
                elif col_upper == 'NOVA SEMANA':
                    header_map['nova_semana'] = idx
                elif col_upper in ('LATITUDE KNVV', 'LATITUDE'):
                    header_map['latitude'] = idx
                elif col_upper in ('LONGITUDE KNVV', 'LONGITUDE'):
                    header_map['longitude'] = idx
            
            required_db_fields = ['cod_cliente', 'razao_social', 'endereco', 'bairro', 'cidade', 'canal_resumido', 'classificacao', 'novo_dia', 'nova_semana']
            missing_fields = [f for f in required_db_fields if f not in header_map]
            
            if missing_fields:
                print("ERRO DE COLUNAS EXCEL. Faltam:", missing_fields)
                raise HTTPException(status_code=400, detail=f"Excel is missing required columns: {missing_fields}")
                
            # Build standard dict list
            for row_cells in sheet.iter_rows(min_row=2, values_only=True):
                # Skip if row is empty or doesn't have the elements we need
                if not row_cells or len(row_cells) <= max(header_map.values()) or len(row_cells) <= route_idx:
                    continue
                row_route = str(row_cells[route_idx] or '').strip()
                if row_route != rota:
                    continue
                rows_to_process.append({
                    'cod_cliente': str(row_cells[header_map['cod_cliente']] or '').strip(),
                    'razao_social': str(row_cells[header_map['razao_social']] or '').strip(),
                    'endereco': str(row_cells[header_map['endereco']] or '').strip(),
                    'bairro': str(row_cells[header_map['bairro']] or '').strip(),
                    'cidade': str(row_cells[header_map['cidade']] or '').strip(),
                    'canal_resumido': str(row_cells[header_map['canal_resumido']] or '').strip(),
                    'classificacao': str(row_cells[header_map['classificacao']] or '').strip(),
                    'novo_dia': str(row_cells[header_map['novo_dia']] or '').strip(),
                    'nova_semana': str(row_cells[header_map['nova_semana']] or '').strip(),
                    'latitude': parse_float(row_cells[header_map['latitude']]) if 'latitude' in header_map else None,
                    'longitude': parse_float(row_cells[header_map['longitude']]) if 'longitude' in header_map else None
                })
        else:
            # Fallback to CSV
            # Decode using utf-8-sig to automatically handle and remove BOM if present
            content_str = contents.decode('utf-8-sig')
            
            # Force semicolon and strip whitespaces from field names
            dialect = csv.excel
            dialect.delimiter = ';'
                
            reader = csv.DictReader(io.StringIO(content_str), dialect=dialect)
            
            # Strip column names to avoid issues with spaces
            if reader.fieldnames:
                reader.fieldnames = [col.strip() for col in reader.fieldnames]
                
            print("COLUNAS ENCONTRADAS NO CSV:", reader.fieldnames)
            
            route_col = None
            if reader.fieldnames:
                for col in reader.fieldnames:
                    if col.strip().upper() == 'NOVA ROTA':
                        route_col = col
                        break
            if route_col is None:
                raise HTTPException(status_code=400, detail="Coluna 'Nova Rota' não encontrada no CSV.")
            
            # Standardize and map headers
            header_map = {}
            if reader.fieldnames:
                for col in reader.fieldnames:
                    col_upper = col.strip().upper()
                    if col_upper.startswith('COD CLIEN') or col_upper.startswith('COD CLIENT') or ('COD' in col_upper and 'CLIEN' in col_upper):
                        header_map['cod_cliente'] = col
                    elif col_upper == 'RAZAO SOCIAL':
                        header_map['razao_social'] = col
                    elif col_upper == 'ENDERECO':
                        header_map['endereco'] = col
                    elif col_upper == 'BAIRRO':
                        header_map['bairro'] = col
                    elif col_upper == 'CIDADE':
                        header_map['cidade'] = col
                    elif col_upper == 'CANAL RESUMIDO':
                        header_map['canal_resumido'] = col
                    elif col_upper in ('CLASSIFICAC', 'CLASSIFICACAO'):
                        header_map['classificacao'] = col
                    elif col_upper == 'NOVO DIA':
                        header_map['novo_dia'] = col
                    elif col_upper == 'NOVA SEMANA':
                        header_map['nova_semana'] = col
                    elif col_upper in ('LATITUDE KNVV', 'LATITUDE'):
                        header_map['latitude'] = col
                    elif col_upper in ('LONGITUDE KNVV', 'LONGITUDE'):
                        header_map['longitude'] = col
 
            required_db_fields = ['cod_cliente', 'razao_social', 'endereco', 'bairro', 'cidade', 'canal_resumido', 'classificacao', 'novo_dia', 'nova_semana']
            missing_fields = [f for f in required_db_fields if f not in header_map]
            
            if missing_fields:
                print("ERRO DE COLUNAS CSV. Faltam:", missing_fields)
                raise HTTPException(status_code=400, detail=f"CSV is missing required columns: {missing_fields}")
                
            for row in reader:
                row_route = str(row.get(route_col) or '').strip()
                if row_route != rota:
                    continue
                rows_to_process.append({
                    'cod_cliente': str(row.get(header_map['cod_cliente']) or '').strip(),
                    'razao_social': str(row.get(header_map['razao_social']) or '').strip(),
                    'endereco': str(row.get(header_map['endereco']) or '').strip(),
                    'bairro': str(row.get(header_map['bairro']) or '').strip(),
                    'cidade': str(row.get(header_map['cidade']) or '').strip(),
                    'canal_resumido': str(row.get(header_map['canal_resumido']) or '').strip(),
                    'classificacao': str(row.get(header_map['classificacao']) or '').strip(),
                    'novo_dia': str(row.get(header_map['novo_dia']) or '').strip(),
                    'nova_semana': str(row.get(header_map['nova_semana']) or '').strip(),
                    'latitude': parse_float(row.get(header_map['latitude'])) if 'latitude' in header_map else None,
                    'longitude': parse_float(row.get(header_map['longitude'])) if 'longitude' in header_map else None
                })
        
        # Clear only this route's database records to support multiple routes
        db.query(Cliente).filter(Cliente.rota == rota).delete()
        
        # Save to DB
        for item in rows_to_process:
            cod_val = item['cod_cliente']
            if not cod_val:
                continue
                
            cliente = Cliente(
                cod_cliente=cod_val,
                razao_social=item['razao_social'],
                endereco=item['endereco'],
                bairro=item['bairro'],
                cidade=item['cidade'],
                canal_resumido=item['canal_resumido'],
                classificacao=item['classificacao'],
                novo_dia=item['novo_dia'],
                nova_semana=item['nova_semana'],
                latitude=item.get('latitude'),
                longitude=item.get('longitude'),
                rota=rota
            )
            db.add(cliente)
        db.commit()
        return {"message": f"Rota {rota} importada com sucesso ({len(rows_to_process)} clientes)!"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": f"Erro ao processar arquivo: {str(e)}"})

@app.post("/api/metas")
async def save_metas(
    meta_sempre_juntos_pct: float = Form(...),
    meta_cerveja_total: int = Form(...),
    meta_cerveja_600ml: int = Form(...),
    meta_cerveja_ln: int = Form(...),
    meta_cerveja_lata: int = Form(...),
    meta_artd: int = Form(...),
    meta_monster: int = Form(...),
    meta_perfetti: int = Form(...),
    meta_campari: int = Form(...),
    db: Session = Depends(get_db)
):
    current_month = get_current_month()
    meta = db.query(MetaMensal).filter(MetaMensal.mes_ano == current_month).first()
    
    if not meta:
        meta = MetaMensal(mes_ano=current_month)
        db.add(meta)
        
    meta.meta_sempre_juntos_pct = meta_sempre_juntos_pct
    meta.meta_cerveja_total = meta_cerveja_total
    meta.meta_cerveja_600ml = meta_cerveja_600ml
    meta.meta_cerveja_ln = meta_cerveja_ln
    meta.meta_cerveja_lata = meta_cerveja_lata
    meta.meta_artd = meta_artd
    meta.meta_monster = meta_monster
    meta.meta_perfetti = meta_perfetti
    meta.meta_campari = meta_campari
    
    db.commit()
    return {"message": "Metas salvas com sucesso!"}

@app.get("/api/metas")
async def get_metas(db: Session = Depends(get_db)):
    current_month = get_current_month()
    meta = db.query(MetaMensal).filter(MetaMensal.mes_ano == current_month).first()
    if not meta:
        return {}
    return {
        "meta_sempre_juntos_pct": meta.meta_sempre_juntos_pct,
        "meta_cerveja_total": meta.meta_cerveja_total,
        "meta_cerveja_600ml": meta.meta_cerveja_600ml,
        "meta_cerveja_ln": meta.meta_cerveja_ln,
        "meta_cerveja_lata": meta.meta_cerveja_lata,
        "meta_artd": meta.meta_artd,
        "meta_monster": meta.meta_monster,
        "meta_campari": meta.meta_campari
    }

@app.get("/api/rotas")
async def get_rotas(db: Session = Depends(get_db)):
    rotas_query = db.query(Cliente.rota).distinct().all()
    return sorted([r[0] for r in rotas_query if r[0]])

@app.get("/api/clientes")
async def get_clientes(
    dia: str = None, 
    semana: str = None, 
    status_meta: str = None, 
    user_lat: float = None, 
    user_lng: float = None, 
    rota: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Cliente)
    if rota:
        query = query.filter(Cliente.rota == rota)
    if dia:
        query = query.filter(Cliente.novo_dia == dia)
    if semana:
        if semana == 'S1':
            query = query.filter((Cliente.nova_semana == 'S1') | (Cliente.nova_semana.contains('S1S3')))
        elif semana == 'S2':
            query = query.filter((Cliente.nova_semana == 'S2') | (Cliente.nova_semana.contains('S2S4')))
        elif semana == 'S3':
            query = query.filter((Cliente.nova_semana == 'S3') | (Cliente.nova_semana.contains('S1S3')))
        elif semana == 'S4':
            query = query.filter((Cliente.nova_semana == 'S4') | (Cliente.nova_semana.contains('S2S4')))
        else:
            query = query.filter(Cliente.nova_semana == semana)
            
    if status_meta and status_meta != 'todos':
        current_month = get_current_month()
        produto_id = None
        
        if status_meta == 'cervejas':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Cervejas").first()
            if prod: produto_id = prod.id
        elif status_meta == 'drinks':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Drinks").first()
            if prod: produto_id = prod.id
        elif status_meta == 'sempre_juntos':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Sempre Juntos").first()
            if prod: produto_id = prod.id
        else:
            # Check if dynamic launch ID
            try:
                produto_id = int(status_meta)
            except ValueError:
                prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == status_meta).first()
                if prod: produto_id = prod.id
                
        if produto_id:
            subquery = db.query(PositivacaoDinamica.cod_cliente).filter(
                PositivacaoDinamica.mes_ano == current_month,
                PositivacaoDinamica.produto_id == produto_id,
                PositivacaoDinamica.valor == True
            ).subquery()
            query = query.filter(Cliente.cod_cliente.in_(subquery))
            
    query = query.order_by(Cliente.razao_social.asc())
    clientes = query.all()
    
    # Progressive Geocoding (max 3 per request to prevent API freezes)
    geocoded_count = 0
    for c in clientes:
        if (c.latitude is None or c.longitude is None) and geocoded_count < 3:
            full_address = f"{c.endereco or ''}, {c.bairro or ''}, {c.cidade or ''} - RJ"
            try:
                lat, lng = geocode_address(full_address)
                if lat and lng:
                    c.latitude = lat
                    c.longitude = lng
                    db.add(c)
                    geocoded_count += 1
            except Exception:
                pass
    if geocoded_count > 0:
        db.commit()
    
    current_month = get_current_month()
    pos_checks = db.query(PositivacaoDinamica).filter(
        PositivacaoDinamica.mes_ano == current_month,
        PositivacaoDinamica.valor == True
    ).all()
    
    products = db.query(ProdutoMeta).all()
    prod_map = {p.id: p.nome_produto for p in products}
    
    client_checks = {}
    for rec in pos_checks:
        prod_name = prod_map.get(rec.produto_id)
        if not prod_name:
            continue
        if rec.cod_cliente not in client_checks:
            client_checks[rec.cod_cliente] = set()
        client_checks[rec.cod_cliente].add(prod_name)
        
    result = []
    for c in clientes:
        checked_names = list(client_checks.get(c.cod_cliente, set()))
        result.append({
            "cod_cliente": c.cod_cliente,
            "razao_social": c.razao_social,
            "endereco": c.endereco,
            "bairro": c.bairro,
            "cidade": c.cidade,
            "canal_resumido": c.canal_resumido,
            "classificacao": c.classificacao,
            "novo_dia": c.novo_dia,
            "nova_semana": c.nova_semana,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "positivados": checked_names
        })
        
    # Geographic Nearest Neighbor reordering
    if user_lat is not None and user_lng is not None:
        have_coords = []
        no_coords = []
        for c in result:
            if c.get("latitude") is not None and c.get("longitude") is not None:
                have_coords.append(c)
            else:
                no_coords.append(c)
                
        ordered_list = []
        current_lat = user_lat
        current_lng = user_lng
        
        # If user coordinates are fallback at (0.0, 0.0) but we have coordinates, use the first client's coords as start point!
        if abs(user_lat) < 0.01 and abs(user_lng) < 0.01 and have_coords:
            current_lat = have_coords[0]["latitude"]
            current_lng = have_coords[0]["longitude"]
            
        while have_coords:
            best_idx = 0
            best_dist = haversine_distance(current_lat, current_lng, have_coords[0]["latitude"], have_coords[0]["longitude"])
            for idx in range(1, len(have_coords)):
                d = haversine_distance(current_lat, current_lng, have_coords[idx]["latitude"], have_coords[idx]["longitude"])
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            best_client = have_coords.pop(best_idx)
            ordered_list.append(best_client)
            current_lat = best_client["latitude"]
            current_lng = best_client["longitude"]
            
        result = ordered_list + no_coords
        
    return result

@app.get("/api/cliente/{cod_cliente}")
async def get_cliente_data(cod_cliente: str, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.cod_cliente == cod_cliente).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    current_month = get_current_month()
    
    # Fetch all active products
    products = db.query(ProdutoMeta).all()
    
    # Fetch positive checks for this client in the current month
    pos_records = db.query(PositivacaoDinamica).filter(
        PositivacaoDinamica.cod_cliente == cod_cliente,
        PositivacaoDinamica.mes_ano == current_month,
        PositivacaoDinamica.valor == True
    ).all()
    
    checked_state = {}
    prod_map = {p.id: p.nome_produto for p in products}
    core_names = ("Cervejas", "Drinks", "Sempre Juntos", "Monster", "Perfetti", "Alcoólicos", "Campari")
    
    for prod in products:
        prod_name = prod.nome_produto
        if prod_name in core_names:
            prod_key = prod_name.lower().replace("á", "a").replace("ó", "o").replace(" ", "_")
            if prod_key == "campari":
                prod_key = "alcoolicos"
            checked_state[prod_key] = False
        else:
            checked_state[f"prod_{prod.id}"] = False
            
    for rec in pos_records:
        prod_name = prod_map.get(rec.produto_id)
        if not prod_name:
            continue
        
        if prod_name in core_names:
            prod_key = prod_name.lower().replace("á", "a").replace("ó", "o").replace(" ", "_")
            if prod_key == "campari":
                prod_key = "alcoolicos"
            
            if rec.sub_item:
                checked_state[f"{prod_key}:{rec.sub_item}"] = True
                checked_state[prod_key] = True
            else:
                checked_state[prod_key] = True
        else:
            checked_state[f"prod_{rec.produto_id}"] = True
            
    return {
        "cliente": {
            "cod_cliente": cliente.cod_cliente,
            "razao_social": cliente.razao_social,
            "endereco": cliente.endereco,
            "bairro": cliente.bairro,
            "cidade": cliente.cidade,
            "canal_resumido": cliente.canal_resumido,
            "classificacao": cliente.classificacao,
            "novo_dia": cliente.novo_dia,
            "nova_semana": cliente.nova_semana
        },
        "positivacao": checked_state
    }

@app.post("/api/positivacao/{cod_cliente}")
async def update_positivacao(cod_cliente: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    current_month = get_current_month()
    
    for key, val in data.items():
        produto_id = None
        sub_item = None
        
        if key == 'sempre_juntos':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Sempre Juntos").first()
            if prod: produto_id = prod.id
        elif key in ('cervejas', 'cerveja_total'):
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Cervejas").first()
            if prod: produto_id = prod.id
        elif key in ('alcoolicos', 'alcoolicos_total'):
            prod = db.query(ProdutoMeta).filter((ProdutoMeta.nome_produto == "Alcoólicos") | (ProdutoMeta.nome_produto == "Campari")).first()
            if prod: produto_id = prod.id
        elif key in ('drinks', 'drinks_total'):
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Drinks").first()
            if prod: produto_id = prod.id
        elif key == 'monster':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Monster").first()
            if prod: produto_id = prod.id
        elif key == 'perfetti':
            prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Perfetti").first()
            if prod: produto_id = prod.id
        elif ":" in key:
            prefix, sub_name = key.split(":", 1)
            prod_name = None
            if prefix == 'cervejas':
                prod_name = "Cervejas"
            elif prefix == 'drinks':
                prod_name = "Drinks"
            elif prefix == 'alcoolicos':
                prod_name = "Alcoólicos"
                
            if prod_name:
                prod = db.query(ProdutoMeta).filter((ProdutoMeta.nome_produto == prod_name) | (ProdutoMeta.nome_produto == "Campari" if prod_name == "Alcoólicos" else False)).first()
                if prod:
                    produto_id = prod.id
                    sub_item = sub_name.strip()
        elif key.startswith('prod_'):
            try:
                produto_id = int(key.replace('prod_', ''))
            except ValueError:
                continue
                
        if produto_id is not None:
            record = db.query(PositivacaoDinamica).filter(
                PositivacaoDinamica.cod_cliente == cod_cliente,
                PositivacaoDinamica.mes_ano == current_month,
                PositivacaoDinamica.produto_id == produto_id,
                PositivacaoDinamica.sub_item == sub_item
            ).first()
            
            if not record:
                record = PositivacaoDinamica(
                    cod_cliente=cod_cliente,
                    mes_ano=current_month,
                    produto_id=produto_id,
                    sub_item=sub_item,
                    mes_referencia=datetime.now().strftime("%m/%Y"),
                    data_registro=datetime.now()
                )
                db.add(record)
            else:
                record.mes_referencia = datetime.now().strftime("%m/%Y")
                record.data_registro = datetime.now()
                
            record.valor = bool(val)
            
            # If master was unchecked, uncheck all sub-items under this product
            if key in ('cervejas', 'cerveja_total', 'alcoolicos', 'alcoolicos_total', 'drinks', 'drinks_total') and not val:
                db.query(PositivacaoDinamica).filter(
                    PositivacaoDinamica.cod_cliente == cod_cliente,
                    PositivacaoDinamica.mes_ano == current_month,
                    PositivacaoDinamica.produto_id == produto_id
                ).update({PositivacaoDinamica.valor: False})
                
    db.commit()
    return {"message": "Salvo"}

@app.get("/api/produtos")
async def get_produtos(db: Session = Depends(get_db)):
    return db.query(ProdutoMeta).all()

@app.post("/api/produtos")
async def add_produto(nome_produto: str = Form(...), meta_quantidade: int = Form(...), db: Session = Depends(get_db)):
    nome_clean = nome_produto.strip()
    if not nome_clean:
        return JSONResponse(status_code=400, content={"message": "Nome do produto não pode ser vazio."})
        
    exists = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == nome_clean).first()
    if exists:
        return JSONResponse(status_code=400, content={"message": "Este produto já existe."})
        
    prod = ProdutoMeta(nome_produto=nome_clean, meta_quantidade=meta_quantidade, obrigatorio_sempre_juntos=False)
    db.add(prod)
    db.commit()
    return {
        "message": f"Produto '{nome_clean}' adicionado com sucesso!",
        "produto": {"id": prod.id, "nome_produto": prod.nome_produto, "meta": prod.meta_quantidade}
    }

@app.get("/api/dashboard")
async def get_dashboard(rota: str = None, db: Session = Depends(get_db)):
    current_month = get_current_month()
    
    meta = db.query(MetaMensal).filter(MetaMensal.mes_ano == current_month).first()
    if not meta:
        # Create default baseline meta to prevent crashes
        meta = MetaMensal(
            mes_ano=current_month,
            meta_sempre_juntos_pct=39.0,
            meta_cerveja_total=10,
            meta_cerveja_600ml=10,
            meta_cerveja_ln=10,
            meta_cerveja_lata=10,
            meta_artd=10,
            meta_monster=10,
            meta_perfetti=10,
            meta_campari=10
        )
        db.add(meta)
        db.commit()

    if not rota:
        first_client = db.query(Cliente).first()
        if first_client:
            rota = first_client.rota
        
    query_clients = db.query(Cliente)
    if rota:
        query_clients = query_clients.filter(Cliente.rota == rota)
        
    total_clients = query_clients.count()
    canais_validos = ['Bar', 'Lanchonete', 'Restaurante', 'Padaria', 'Mercearia']
    clientes_validos_count = query_clients.filter(Cliente.canal_resumido.in_(canais_validos)).count()
    
    products = db.query(ProdutoMeta).all()
    
    realizado = {}
    metas_dict = {}
    
    prod_sj = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Sempre Juntos").first()
    prod_cervejas = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Cervejas").first()
    prod_drinks = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Drinks").first()
    
    if prod_sj:
        sj_query = db.query(PositivacaoDinamica).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_sj.id,
            PositivacaoDinamica.valor == True,
            Cliente.canal_resumido.in_(canais_validos)
        )
        if rota:
            sj_query = sj_query.filter(Cliente.rota == rota)
            
        sj_count = sj_query.count()
        sj_pct = round((sj_count / clientes_validos_count * 100), 1) if clientes_validos_count > 0 else 0.0
        realizado["sempre_juntos_pct"] = sj_pct
        metas_dict["sempre_juntos_pct"] = meta.meta_sempre_juntos_pct
        
    if prod_cervejas:
        cv_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_cervejas.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            cv_query = cv_query.filter(Cliente.rota == rota)
            
        cv_count = cv_query.distinct().count()
        realizado["cerveja_total"] = cv_count
        metas_dict["cerveja_total"] = meta.meta_cerveja_total
        
        # Pull sub-items positive checks to aggregate dynamically
        sub_query = db.query(PositivacaoDinamica).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_cervejas.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            sub_query = sub_query.filter(Cliente.rota == rota)
            
        cervejas_pos = sub_query.all()
        c_600ml_clients = set()
        c_ln_clients = set()
        c_lata_clients = set()
        
        for p_rec in cervejas_pos:
            sub = (p_rec.sub_item or '').lower()
            if not sub:
                continue
            if '600ml' in sub or '500ml' in sub or 'vidro' in sub:
                c_600ml_clients.add(p_rec.cod_cliente)
            elif 'ln' in sub or 'long neck' in sub:
                c_ln_clients.add(p_rec.cod_cliente)
            elif 'lata' in sub:
                c_lata_clients.add(p_rec.cod_cliente)
                
        realizado["cerveja_600ml"] = len(c_600ml_clients)
        realizado["cerveja_ln"] = len(c_ln_clients)
        realizado["cerveja_lata"] = len(c_lata_clients)
        
        metas_dict["cerveja_600ml"] = meta.meta_cerveja_600ml
        metas_dict["cerveja_ln"] = meta.meta_cerveja_ln
        metas_dict["cerveja_lata"] = meta.meta_cerveja_lata
            
    if prod_drinks:
        drinks_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_drinks.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            drinks_query = drinks_query.filter(Cliente.rota == rota)
            
        drinks_count = drinks_query.distinct().count()
        realizado["drinks"] = drinks_count
        metas_dict["drinks"] = meta.meta_artd
        
    prod_monster = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Monster").first()
    if prod_monster:
        monster_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_monster.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            monster_query = monster_query.filter(Cliente.rota == rota)
            
        monster_count = monster_query.distinct().count()
        realizado["monster"] = monster_count
        metas_dict["monster"] = meta.meta_monster
        
    prod_perfetti = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Perfetti").first()
    if prod_perfetti:
        perfetti_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_perfetti.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            perfetti_query = perfetti_query.filter(Cliente.rota == rota)
            
        perfetti_count = perfetti_query.distinct().count()
        realizado["perfetti"] = perfetti_count
        metas_dict["perfetti"] = meta.meta_perfetti
        
    prod_alcoolicos = db.query(ProdutoMeta).filter((ProdutoMeta.nome_produto == "Alcoólicos") | (ProdutoMeta.nome_produto == "Campari")).first()
    if prod_alcoolicos:
        alcoolicos_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == prod_alcoolicos.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            alcoolicos_query = alcoolicos_query.filter(Cliente.rota == rota)
            
        alcoolicos_count = alcoolicos_query.distinct().count()
        realizado["campari"] = alcoolicos_count
        metas_dict["campari"] = meta.meta_campari
        
    dynamic_products = [p for p in products if p.nome_produto not in ("Cervejas", "Drinks", "Sempre Juntos", "Monster", "Perfetti", "Campari", "Alcoólicos")]
    launches_realizado = []
    
    for lp in dynamic_products:
        lp_query = db.query(PositivacaoDinamica.cod_cliente).join(
            Cliente, Cliente.cod_cliente == PositivacaoDinamica.cod_cliente
        ).filter(
            PositivacaoDinamica.mes_ano == current_month,
            PositivacaoDinamica.produto_id == lp.id,
            PositivacaoDinamica.valor == True
        )
        if rota:
            lp_query = lp_query.filter(Cliente.rota == rota)
            
        count = lp_query.distinct().count()
        
        launches_realizado.append({
            "id": lp.id,
            "nome_produto": lp.nome_produto,
            "realizado": count,
            "meta": lp.meta_quantidade or 10
        })
        
    return {
        "metas": metas_dict,
        "realizado": realizado,
        "launches": launches_realizado,
        "total_clientes": total_clients,
        "clientes_validos_sj": clientes_validos_count
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
