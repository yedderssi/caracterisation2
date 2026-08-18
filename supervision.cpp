#include "supervision.h"
#include "ui_supervision.h"

supervision::supervision(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::supervision)
{
    ui->setupUi(this);
}

supervision::~supervision()
{
    delete ui;
}
