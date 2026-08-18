#ifndef PAGE_ACQUISITION_H
#define PAGE_ACQUISITION_H

#include <QDialog>

namespace Ui {
class Page_acquisition;
}

class Page_acquisition : public QDialog
{
    Q_OBJECT

public:
    explicit Page_acquisition(QWidget *parent = nullptr);
    ~Page_acquisition();

private:
    Ui::Page_acquisition *ui;
};

#endif // PAGE_ACQUISITION_H
