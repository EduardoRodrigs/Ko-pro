from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Normalize postgres:// to postgresql:// for SQLAlchemy 1.4+ compatibility
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    db_path = os.getenv("DATABASE_PATH", "./andina_pro.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Cliente(Base):
    __tablename__ = "clientes"

    cod_cliente = Column(String, primary_key=True, index=True)
    razao_social = Column(String, index=True)
    endereco = Column(String)
    bairro = Column(String)
    cidade = Column(String)
    canal_resumido = Column(String)
    classificacao = Column(String)
    novo_dia = Column(String)
    nova_semana = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    rota = Column(String, index=True, nullable=True)

class MetaMensal(Base):
    __tablename__ = "metas_mensais"

    id = Column(Integer, primary_key=True, index=True)
    mes_ano = Column(String, index=True) # format: YYYY-MM
    rota = Column(String, index=True, nullable=True)
    meta_sempre_juntos_pct = Column(Float, default=0.0)
    meta_cerveja_total = Column(Integer, default=0)
    meta_cerveja_600ml = Column(Integer, default=0)
    meta_cerveja_ln = Column(Integer, default=0)
    meta_cerveja_lata = Column(Integer, default=0)
    meta_artd = Column(Integer, default=0)
    meta_monster = Column(Integer, default=0)
    meta_perfetti = Column(Integer, default=0)
    meta_campari = Column(Integer, default=0)

    # Constraint to ensure unique target metrics per route per month
    __table_args__ = (UniqueConstraint('mes_ano', 'rota', name='_mes_ano_rota_uc'),)

class ProdutoMeta(Base):
    __tablename__ = "produtos_meta"

    id = Column(Integer, primary_key=True, index=True)
    nome_produto = Column(String, unique=True, index=True)
    obrigatorio_sempre_juntos = Column(Boolean, default=False)
    meta_quantidade = Column(Integer, default=10)

class PositivacaoDinamica(Base):
    __tablename__ = "positivacoes_dinamicas"

    id = Column(Integer, primary_key=True, index=True)
    cod_cliente = Column(String, index=True)
    mes_ano = Column(String, index=True)
    produto_id = Column(Integer, index=True)
    sub_item = Column(String, nullable=True) # '600ml', 'ln', 'lata'
    valor = Column(Boolean, default=False)
    mes_referencia = Column(String, index=True, nullable=True) # format: MM/YYYY
    data_registro = Column(DateTime, default=datetime.utcnow, nullable=True)
    rota = Column(String, index=True, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe migrations for new columns
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE positivacoes_dinamicas ADD COLUMN mes_referencia VARCHAR;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE positivacoes_dinamicas ADD COLUMN data_registro TIMESTAMP;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE clientes ADD COLUMN rota VARCHAR;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE metas_mensais ADD COLUMN rota VARCHAR;"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE positivacoes_dinamicas ADD COLUMN rota VARCHAR;"))
        except Exception:
            pass
    # Populate initial products
    db = SessionLocal()
    try:
        # Check if Campari needs to be renamed to Alcoólicos
        campari_prod = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == "Campari").first()
        if campari_prod:
            campari_prod.nome_produto = "Alcoólicos"
            db.commit()
            
        defaults = [
            ("Cervejas", False),
            ("Drinks", False),
            ("Sempre Juntos", True),
            ("Monster", False),
            ("Perfetti", False),
            ("Alcoólicos", False)
        ]
        for name, req_sj in defaults:
            exists = db.query(ProdutoMeta).filter(ProdutoMeta.nome_produto == name).first()
            if not exists:
                prod = ProdutoMeta(nome_produto=name, obrigatorio_sempre_juntos=req_sj)
                db.add(prod)
        db.commit()
    except Exception as e:
        print("Erro ao popular produtos iniciais:", e)
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

