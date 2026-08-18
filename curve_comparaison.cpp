#include "curve_comparaison.h"
#include "ui_curve_comparaison.h"

curve_comparaison::curve_comparaison(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::curve_comparaison)
{
    ui->setupUi(this);
}

curve_comparaison::~curve_comparaison()
{
    delete ui;
}
