-- credentials-db: usado por auth_service e recovery_service
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil ENUM('paciente', 'medico', 'administrador') NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT NOW(),
    atualizado_em DATETIME NULL
);
