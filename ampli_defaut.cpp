#include "ampli_defaut.h"
#include "ui_ampli_defaut.h"

Ampli_defaut::Ampli_defaut(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::Ampli_defaut)
{
    ui->setupUi(this);
}

Ampli_defaut::~Ampli_defaut()
{
    delete ui;
}
