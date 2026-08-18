#include "ampli.h"
#include "ui_ampli.h"

Ampli::Ampli(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::Ampli)
{
    ui->setupUi(this);
}

Ampli::~Ampli()
{
    delete ui;
}
