#include "pertesvsfreq.h"
#include "ui_pertesvsfreq.h"

PertesVsFreq::PertesVsFreq(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::PertesVsFreq)
{
    ui->setupUi(this);
}

PertesVsFreq::~PertesVsFreq()
{
    delete ui;
}
