CREATE TABLE IF NOT EXISTS especialidades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS medicos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    email_profissional VARCHAR(150) NOT NULL UNIQUE,
    telefone_profissional VARCHAR(20) NULL,
    especialidade_id INT NOT NULL,
    crm VARCHAR(20) NOT NULL UNIQUE,
    FOREIGN KEY (especialidade_id) REFERENCES especialidades(id)
);

INSERT IGNORE INTO especialidades (nome) VALUES
    ('Cardiologia'),('Dermatologia'),('Ortopedia'),('Pediatria'),('Clinica Geral');