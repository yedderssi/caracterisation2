#ifndef AMPLI_DEFAUT_H
#define AMPLI_DEFAUT_H

#include <QDialog>

namespace Ui {
class Ampli_defaut;
}

class Ampli_defaut : public QDialog
{
    Q_OBJECT

public:
    explicit Ampli_defaut(QWidget *parent = nullptr);
    ~Ampli_defaut();

private:
    Ui::Ampli_defaut *ui;
};

#endif // AMPLI_DEFAUT_H
