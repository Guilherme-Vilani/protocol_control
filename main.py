import firebase_admin
from firebase_admin import credentials, firestore, storage
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query
from typing import List, Optional
import json
import uuid
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Inicializa o Firebase
cred = credentials.Certificate("") # colocar o arquivo
firebase_admin.initialize_app(cred, {"storageBucket": "fmo-medicine.firebasestorage.app"})

db = firestore.client()
bucket = storage.bucket()

async def get_next_protocol_id():
    """ Obtém o próximo ID auto-incrementado da coleção metadata. """
    counter_ref = db.collection("metadata").document("protocol_counter")
    counter_doc = counter_ref.get()

    if counter_doc.exists:
        last_id = counter_doc.to_dict().get("last_id", 0)
    else:
        last_id = 0

    new_id = last_id + 1

    # Atualiza o contador global
    counter_ref.set({"last_id": new_id})

    return new_id


@app.get("/get-protocols/")
async def get_protocols():
    try:
        users_ref = db.collection("protocols").stream()
        
        protocols = []
        for user in users_ref:
            protocol_data = user.to_dict()
            protocol_data["id"] = user.id  # Adiciona o ID do documento
            if "dt_abertura_protocolo" in protocol_data:
                protocol_data["dt_abertura_protocolo"] = protocol_data["dt_abertura_protocolo"].isoformat()  # Formata data
            protocols.append(protocol_data)

        return {"protocols": protocols}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search-protocols/")
async def search_protocols(
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    cpf: Optional[str] = Query(None, description="Filtrar por CPF"),
    matricula: Optional[str] = Query(None, description="Filtrar por Matrícula")
):
    try:
        query = db.collection("protocols")
        
        if id is not None:
            query = query.where("id", "==", id)
        if cpf:
            query = query.where("cpf", "==", cpf)
        if matricula:
            query = query.where("matricula", "==", matricula)

        results = query.stream()
        
        protocols = []
        for doc in results:
            data = doc.to_dict()
            data["id"] = doc.id
            protocols.append(data)

        return {"protocols": protocols}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/insert-protocol/")
async def add_protocol(
    protocol_data: str = Form(...),
    files: Optional[List[UploadFile]] = File(None)
):
    try:
        data = json.loads(protocol_data)

        urls = []
        if files:
            for file in files:
                file_extension = file.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"

                blob = bucket.blob(f"uploads/{file_name}")
                blob.upload_from_file(file.file, content_type=file.content_type)
                blob.make_public()
                urls.append(blob.public_url)

        protocol_id = await get_next_protocol_id()

        doc_ref = db.collection("protocols").document(str(protocol_id))
        doc_ref.set({
            "id": protocol_id,
            "nome": data["nome"],
            "email": data["email"],
            "cpf": data["cpf"],
            "telefone": data["telefone"],
            "matricula": data["matricula"],
            "assunto": data["assunto"],
            "mensagem": data["mensagem"],
            "dt_abertura_protocolo": datetime.utcnow(),
            "anexos": urls,
            "status": "pendente"
        })

        return {"message": "Protocolo criado com sucesso!", "id": protocol_id, "anexos": urls}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Erro ao processar os dados. JSON inválido.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.put("/update-status/{protocol_id}")
async def update_protocol_status(protocol_id: str):
    try:
        doc_ref = db.collection("protocols").document(protocol_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

        doc_ref.update({"status": "respondido"})

        return {"message": "Protocolo atualizado para 'respondido' com sucesso!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

