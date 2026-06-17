-- scheduling-db: usado por scheduling_service
CREATE TABLE IF NOT EXISTS horarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medico_id INT NOT NULL,
    data_hora DATETIME NOT NULL,
    disponivel BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_medico_horario (medico_id, data_hora)
);

CREATE TABLE IF NOT EXISTS consultas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    medico_id INT NOT NULL,
    horario_id INT NOT NULL,
    status ENUM('agendada', 'confirmada', 'concluida', 'cancelada', 'falta') NOT NULL DEFAULT 'agendada',
    observacoes TEXT NULL,
    criado_em DATETIME NOT NULL DEFAULT NOW(),
    atualizado_em DATETIME NULL,
    FOREIGN KEY (horario_id) REFERENCES horarios(id)
);
