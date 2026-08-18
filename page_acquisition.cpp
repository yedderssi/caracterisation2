#include "page_acquisition.h"
#include "ui_page_acquisition.h"

Page_acquisition::Page_acquisition(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::Page_acquisition)
{
    ui->setupUi(this);
}

Page_acquisition::~Page_acquisition()
{
    delete ui;
}
